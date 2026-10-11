"""Generator napisów: transkrypcja (faster-whisper), podział na napisy, SRT i tłumaczenie (Claude CLI / Claude API / DeepL)."""
import json
import os
import re
import sys
import textwrap
import threading
from dataclasses import dataclass, replace

from i18n import t

# kod: (nazwa polska, nazwa angielska, kod docelowy DeepL lub None)
LANGUAGES = {
    "pl": ("polski", "Polish", "PL"),
    "en": ("angielski", "English", "EN-US"),
    "de": ("niemiecki", "German", "DE"),
    "fr": ("francuski", "French", "FR"),
    "es": ("hiszpański", "Spanish", "ES"),
    "it": ("włoski", "Italian", "IT"),
    "pt": ("portugalski", "Portuguese", "PT-PT"),
    "nl": ("niderlandzki", "Dutch", "NL"),
    "uk": ("ukraiński", "Ukrainian", "UK"),
    "ru": ("rosyjski", "Russian", "RU"),
    "cs": ("czeski", "Czech", "CS"),
    "sk": ("słowacki", "Slovak", "SK"),
    "lt": ("litewski", "Lithuanian", "LT"),
    "lv": ("łotewski", "Latvian", "LV"),
    "et": ("estoński", "Estonian", "ET"),
    "hu": ("węgierski", "Hungarian", "HU"),
    "ro": ("rumuński", "Romanian", "RO"),
    "bg": ("bułgarski", "Bulgarian", "BG"),
    "el": ("grecki", "Greek", "EL"),
    "sv": ("szwedzki", "Swedish", "SV"),
    "no": ("norweski", "Norwegian", "NB"),
    "da": ("duński", "Danish", "DA"),
    "fi": ("fiński", "Finnish", "FI"),
    "tr": ("turecki", "Turkish", "TR"),
    "ar": ("arabski", "Arabic", "AR"),
    "zh": ("chiński", "Chinese", "ZH-HANS"),
    "ja": ("japoński", "Japanese", "JA"),
    "ko": ("koreański", "Korean", "KO"),
    "id": ("indonezyjski", "Indonesian", "ID"),
    "he": ("hebrajski", "Hebrew", None),
    "vi": ("wietnamski", "Vietnamese", None),
    "hi": ("hindi", "Hindi", None),
}


def lang_name(code):
    """Nazwa w języku interfejsu; dla języków spoza listy (wpisanych ręcznie) — to, co wpisano."""
    import i18n

    return LANGUAGES[code][0 if i18n.LANG == "pl" else 1] if code in LANGUAGES else code


def resolve_language(text):
    """'fr' / 'francuski' / 'French' → 'fr'. Nieznana nazwa zostaje jak jest (tylko dla tłumaczy LLM)."""
    t = text.strip()
    for code, (pl, en, _) in LANGUAGES.items():
        if t.lower() in (code, pl.lower(), en.lower()):
            return code
    return t


def file_suffix(lang):
    return lang if lang in LANGUAGES else (re.sub(r"\W+", "_", lang.lower()).strip("_") or "xx")


# ---------------------------------------------------------------- przerywanie (przycisk Stop)

CANCEL = threading.Event()


class Cancelled(Exception):
    pass


class AlreadyReported(Exception):
    """Błąd został już wypisany w logu (np. wszystkie tłumaczenia się nie udały)."""


def check_cancel():
    if CANCEL.is_set():
        raise Cancelled()


_ACTIVE = set()  # uruchomione procesy tłumaczy (do zabicia przy Stop / zamknięciu okna)
_ACTIVE_LOCK = threading.Lock()


def _kill_tree(proc):
    """Zabija proces razem z potomkami (np. shim npm → node → właściwy codex)."""
    import signal
    import subprocess

    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.killpg(proc.pid, signal.SIGKILL)  # proces startuje we własnej grupie (start_new_session)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def kill_active():
    """Natychmiast zabija wszystkie uruchomione procesy tłumaczy (zamknięcie okna)."""
    CANCEL.set()
    with _ACTIVE_LOCK:
        procs = list(_ACTIVE)
    for proc in procs:
        _kill_tree(proc)


def _run_proc(cmd, input_text, cwd=None):
    """subprocess.run, który da się przerwać przyciskiem Stop (zabija całe drzewo procesów)."""
    import subprocess
    import tempfile

    win = sys.platform == "win32"
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if win else 0
    # osobny pusty katalog roboczy: CLI nie wczyta CLAUDE.md ani ustawień z bieżącego folderu
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", cwd=cwd or tmp, creationflags=flags,
                                start_new_session=not win,
                                env=dict(os.environ, PATH=search_path()))  # np. skrypt npm potrzebuje `node`
        with _ACTIVE_LOCK:
            _ACTIVE.add(proc)
        try:
            pending = input_text
            while True:
                try:
                    out, err = proc.communicate(pending, timeout=0.3)
                    if CANCEL.is_set():
                        raise Cancelled()
                    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
                except subprocess.TimeoutExpired:
                    pending = None  # stdin wysłane przy pierwszym wywołaniu
                    if CANCEL.is_set():
                        _kill_tree(proc)
                        proc.communicate()
                        raise Cancelled()
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(proc)


@dataclass
class Cue:
    start: float
    end: float
    text: str


@dataclass
class Word:
    start: float
    end: float
    word: str


# ---------------------------------------------------------------- transkrypcja

_cuda_ready = False


def _add_cuda_dll_paths():
    """Pakiety nvidia-cublas-cu12 / nvidia-cudnn-cu12 trzymają biblioteki w site-packages/nvidia/*/(bin|lib)."""
    global _cuda_ready
    if _cuda_ready or sys.platform == "darwin":
        return
    _cuda_ready = True
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for sub in sorted(os.listdir(base)):  # cublas przed cudnn
            if sys.platform == "win32":
                bin_dir = os.path.join(base, sub, "bin")
                if os.path.isdir(bin_dir):
                    os.add_dll_directory(bin_dir)
                    os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]
            else:  # Linux: LD_LIBRARY_PATH nie działa po starcie procesu, więc ładujemy .so ręcznie
                import ctypes
                import glob

                for so in sorted(glob.glob(os.path.join(base, sub, "lib", "lib*.so*"))):
                    try:
                        ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
                    except OSError:
                        pass


_LOADED = {}  # (model, urządzenie) → WhisperModel; zostaje w pamięci między plikami i zadaniami


def _load_model(model_name, device, log, progress):
    from faster_whisper import WhisperModel

    key = (model_name, device)
    if key not in _LOADED:
        if not model_cached(model_name):  # nigdy nie pobieramy po cichu — GUI i CLI pytają wcześniej
            raise RuntimeError(t("model_not_downloaded", model=model_name))
        log(t("loading_model", model=model_name, dev="GPU" if device == "cuda" else "CPU"))
        progress(None, t("stage_loading"))
        model = WhisperModel(model_name, device=device, compute_type="float16" if device == "cuda" else "int8",
                             local_files_only=True)
        _LOADED.clear()  # jeden model naraz (pamięć karty) — dopiero gdy nowy się załadował
        _LOADED[key] = model
    return _LOADED[key]


def _decode(path):
    """Dźwięk z pliku (16 kHz mono). Nieczytelny plik → zrozumiały komunikat zamiast błędu FFmpeg."""
    from faster_whisper import decode_audio

    try:
        return decode_audio(path)
    except Exception as e:
        if type(e).__module__.startswith("av"):  # błędy PyAV/FFmpeg: uszkodzony plik, brak ścieżki audio…
            raise RuntimeError(t("cant_read_media", name=os.path.basename(path))) from e
        raise


def _run_whisper(path, language, model_name, device, log, progress):
    model = _load_model(model_name, device, log, progress)
    audio = _decode(path)
    check_cancel()
    if language:
        # Whisper z wymuszonym złym językiem nie zapisuje mowy, tylko ją (słabo) tłumaczy — sprawdzamy to
        detected, prob, _ = model.detect_language(audio, vad_filter=True, language_detection_segments=3)
        if detected != language and prob >= 0.8:
            log(t("lang_mismatch", chosen=lang_name(language), detected=lang_name(detected), prob=prob))
            language = detected
    segments, info = model.transcribe(
        audio,
        language=language,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    log(t("detected", lang=lang_name(info.language), prob=info.language_probability, mins=info.duration / 60))
    words = []
    for seg in segments:
        check_cancel()
        for w in seg.words or []:
            words.append(Word(w.start, w.end, w.word))
        if info.duration:
            progress(min(seg.end / info.duration, 1.0), t("stage_stt"))
    return words, info.language


# repozytoria modeli na Hugging Face (jak w faster_whisper.utils._MODELS) — bez importu faster_whisper,
# który przy starcie okna kosztowałby ułamek sekundy
WHISPER_REPOS = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "medium": "Systran/faster-whisper-medium",
}


def _model_dir(model_name):
    """Katalog modelu w cache Hugging Face (te same zmienne środowiskowe co huggingface_hub)."""
    cache = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if not cache:
        home = os.environ.get("HF_HOME") or os.path.join(
            os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"), "huggingface")
        cache = os.path.join(home, "hub")
    repo = WHISPER_REPOS.get(model_name)
    if repo is None:
        from faster_whisper.utils import _MODELS

        repo = _MODELS.get(model_name, model_name)
    return os.path.join(os.path.expanduser(cache), "models--" + repo.replace("/", "--"))


def model_cached(model_name):
    """Czy model Whisper jest już pobrany: model.bin w snapshots/ pojawia się dopiero po pobraniu całego pliku."""
    import glob

    return bool(glob.glob(os.path.join(glob.escape(_model_dir(model_name)), "snapshots", "*", "model.bin")))


def _downloaded_bytes(model_dir):
    """Bajty pobrane do cache modelu: pliki w blobs/ (także *.incomplete) i — gdy system nie pozwala na
    dowiązania (Windows bez trybu dewelopera) — pliki przeniesione do snapshots/. Dowiązań nie liczymy
    podwójnie. getsize, nie scandir: na Windows scandir podaje nieaktualny rozmiar zapisywanego pliku."""
    total = 0
    for root, _, files in os.walk(model_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                if not os.path.islink(path):
                    total += os.path.getsize(path)
            except OSError:
                pass  # plik właśnie przenoszony
    return total


def download_model(model_name, progress=lambda done, total: None, cancel=None):
    """Pobiera model Whisper w osobnym procesie — anulowanie (cancel.set()) od razu go zabija.

    progress(done, total) w bajtach: postęp liczony z rozmiaru plików w cache (działa też z hf_xet);
    nigdy się nie cofa."""
    import subprocess
    import tempfile
    import time

    model_dir = _model_dir(model_name)
    total = int(WHISPER_SIZES.get(model_name, 0) * 1e9)
    shown = 0
    win = sys.platform == "win32"
    code = "import sys; from faster_whisper.utils import download_model; download_model(sys.argv[1])"
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(
            [sys.executable, "-c", code, model_name], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=err, creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if win else 0,
            start_new_session=not win)
        with _ACTIVE_LOCK:
            _ACTIVE.add(proc)  # zamknięcie okna też przerywa pobieranie
        try:
            while proc.poll() is None:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                shown = max(shown, min(_downloaded_bytes(model_dir), total))
                progress(shown, total)
                time.sleep(0.4)
        except BaseException:  # anulowanie, Ctrl+C w CLI, błąd w progress — proces pobierania nie może zostać
            _kill_tree(proc)
            proc.wait()
            raise
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(proc)
        if proc.returncode or not model_cached(model_name):
            err.seek(0)
            lines = [x for x in err.read().strip().splitlines() if x.strip()]
            raise RuntimeError(t("download_failed", model=model_name, err=lines[-1] if lines else proc.returncode))
    progress(total, total)


_gpu_usable = None  # None = nie wiadomo; False po pierwszej porażce — potem od razu CPU


def gpu_available():
    global _gpu_usable
    if _gpu_usable is None:
        if sys.platform == "darwin":  # CTranslate2 na macOS nie ma CUDA
            _gpu_usable = False
        else:
            try:
                _add_cuda_dll_paths()
                import ctranslate2

                _gpu_usable = ctranslate2.get_cuda_device_count() > 0
            except Exception:
                _gpu_usable = False
    return _gpu_usable


def _on_gpu_or_cpu(run, log):
    """run(device): na GPU, jeśli jest; gdy CUDA zawiedzie — CPU (i zapamiętujemy to do końca sesji)."""
    global _gpu_usable
    if not gpu_available():
        return run("cpu")
    try:
        return run("cuda")
    except Cancelled:
        raise
    except Exception as e:  # brak cuDNN, nieobsługiwana karta, za mało pamięci GPU…
        if not any(w in str(e).lower() for w in ("cuda", "cublas", "cudnn", "gpu", ".dll", ".so", "out of memory")):
            raise  # np. uszkodzony plik — CPU nic tu nie pomoże
        log(t("gpu_failed", err=e))
        _gpu_usable = False
        return run("cpu")


def transcribe(path, language, model_name, log, progress):
    """Zwraca (lista słów z czasami, wykryty język)."""
    return _on_gpu_or_cpu(lambda device: _run_whisper(path, language, model_name, device, log, progress), log)


def detect_language(path, model_name, log, progress=lambda v, stage=None: None):
    """Szybkie wykrycie języka mowy (bez transkrypcji)."""
    def run(device):
        model = _load_model(model_name, device, log, progress)
        progress(None, t("stage_detect"))
        lang, prob, _ = model.detect_language(_decode(path), vad_filter=True, language_detection_segments=3)
        log(t("detected_short", lang=lang_name(lang), prob=prob))
        return lang
    return _on_gpu_or_cpu(run, log)


# ---------------------------------------------------------------- podział na napisy

SENTENCE_END = (".", "?", "!", "…", "。", "？", "！")
CLAUSE_END = (",", ";", ":", "–", "-", "，", "、", "；", "：")
# języki pisane bez spacji między słowami: Whisper zwraca je znak po znaku, linie liczymy krócej
NO_SPACE = {"zh", "ja", "th", "lo", "my", "yue", "km"}
NO_SPACE_CHARS = 16  # zalecana długość linii napisów dla chińskiego/japońskiego


def line_chars(lang, chars):
    """Długość linii dla języka: dla języków bez spacji najwyżej NO_SPACE_CHARS."""
    return min(chars, NO_SPACE_CHARS) if lang in NO_SPACE else chars
ABBREV = {"m.in.", "np.", "tzn.", "tj.", "itd.", "itp.", "ok.", "ul.", "dr.", "prof.", "godz.", "r.",
          "z.b.", "bzw.", "usw.", "ca.", "e.g.", "i.e.", "etc.", "vs.", "mr.", "mrs.", "dr"}
# przed tymi słowami wolno zacząć nowy napis
CONJ = {"i", "a", "ale", "oraz", "lub", "albo", "czy", "że", "żeby", "bo", "więc", "gdy", "kiedy", "który",
        "która", "które", "and", "but", "or", "so", "because", "that", "which", "when",
        "und", "aber", "oder", "dass", "weil", "wenn", "denn"}


def _join(words):
    return "".join(w.word for w in words).strip()


def _sentence_end(w):
    t = w.word.strip()
    return t.endswith(SENTENCE_END) and t.lower() not in ABBREV and not re.fullmatch(r"\w\.", t)


def _merge_fragments(words):
    """Whisper czasem tnie słowo na kawałki („m” + „.in.”) — kawałek bez spacji doklejamy do poprzedniego."""
    out = []
    for w in words:
        if out and not w.word.startswith(" "):
            out[-1] = Word(out[-1].start, w.end, out[-1].word + w.word)
        else:
            out.append(Word(w.start, w.end, w.word))
    return out


def build_cues(words, max_chars=42, max_lines=2, max_dur=6.0, max_gap=0.7, lang=None):
    if lang in NO_SPACE:
        max_chars = line_chars(lang, max_chars)  # słowa bez spacji — nie sklejamy ich w „jedno słowo”
    else:
        words = _merge_fragments(words)
    limit = max_chars * max_lines
    soft = int(max_chars * 0.7)
    cues, cur = [], []

    def flush(n=None):
        n = len(cur) if n is None else n
        part = cur[:n]
        if part:
            cues.append(Cue(part[0].start, part[-1].end, _join(part)))
        del cur[:n]

    def sentence_fits(i):
        """Czy reszta zdania (od słowa i) zmieści się w bieżącym napisie?"""
        rest = []
        for w in words[i:]:
            rest.append(w)
            if len(_join(cur + rest)) > limit or w.end - cur[0].start > max_dur:
                return False
            if _sentence_end(w):
                return True
        return True

    for i, w in enumerate(words):
        if cur:
            too_long = len(_join(cur + [w])) > limit
            if too_long or w.start - cur[-1].end > max_gap or w.end - cur[0].start > max_dur:
                # jeśli się da, tniemy po przecinku / przed spójnikiem w drugiej połowie napisu
                cut = next((k + 1 for k in range(len(cur) - 1, len(cur) // 2 - 1, -1)
                            if cur[k].word.strip().endswith(CLAUSE_END[:1] + CLAUSE_END[-4:])
                            or (k + 1 < len(cur) and cur[k + 1].word.strip().lower() in CONJ)), None)
                flush(cut if too_long else None)
            elif (len(_join(cur)) >= soft
                  and (cur[-1].word.strip().endswith(CLAUSE_END)
                       or w.word.strip().lower() in CONJ)
                  and not sentence_fits(i)):
                flush()  # naturalna pauza w długim zdaniu
        cur.append(w)
        if _sentence_end(w) and len(_join(cur)) >= (4 if lang in NO_SPACE else 12):
            flush()
    flush()
    return fix_timing(cues)


def fix_timing(cues, min_dur=1.0, tail=0.2, gap=0.04):
    """Każdy napis min. 1 s i lekko przedłużony, ale nie nachodzi na następny."""
    for i, c in enumerate(cues):
        nxt = cues[i + 1].start - gap if i + 1 < len(cues) else float("inf")
        c.end = min(max(c.end + tail, c.start + min_dur), max(nxt, c.end))
    return cues


def _break_cost(text, i, max_chars):
    left, right = text[:i], text[i + 1:]
    cost = abs(len(left) - len(right))
    if max(len(left), len(right)) > max_chars:
        cost += 1000
    last = left.rsplit(" ", 1)[-1]
    if left.endswith((",", ".", ";", ":", "?", "!")):
        cost -= 12
    if len(last) == 1 and last.isalpha():  # polska typografia: bez „w”, „i”, „z” na końcu linii
        cost += 40
    if right.split(" ", 1)[0].lower() in CONJ:
        cost -= 6
    return cost


def _wrap_no_space(text, max_chars):
    """Tekst bez spacji (chiński, japoński…): równe linie, cięcie najchętniej po znaku interpunkcji."""
    lines = []
    while len(text) > max_chars:
        n_lines = -(-len(text) // max_chars)
        target = -(-len(text) // n_lines)
        cut = next((i + 1 for i in range(target, max(target - 5, 0), -1)
                    if i < len(text) and text[i] in "，、。？！,.?!"), target)
        lines.append(text[:cut])
        text = text[cut:]
    return "\n".join(lines + [text])


def wrap(text, max_chars=42, max_lines=2):
    """Dzieli tekst na linie: równe długości, cięcie po przecinku, bez jednoliterowych słów na końcu.
    Gdy tekst (np. dłuższe tłumaczenie) nie mieści się w max_lines liniach, linie robią się dłuższe."""
    text = " ".join(text.split())
    if len(text) <= max_chars or max_lines <= 1:
        return text
    spaces = [m.start() for m in re.finditer(" ", text)]
    if not spaces or len(spaces) < len(text) / 25:  # pismo bez spacji (lub prawie bez)
        return _wrap_no_space(text, max_chars)
    if max_lines == 2 or len(text) <= 2 * max_chars + 5:
        width = max(max_chars, -(-len(text) // 2) + 5)
        best = min(spaces, key=lambda i: _break_cost(text, i, width))
        return text[:best] + "\n" + text[best + 1:]
    return "\n".join(textwrap.wrap(text, max(max_chars, -(-len(text) // max_lines) + 3)))


# ---------------------------------------------------------------- zapis: SRT / WebVTT / ASS / TXT

FORMATS = {
    "srt": "SRT",
    "vtt": "WebVTT",
    "ass": "ASS",
    "txt": "TXT",  # sam tekst, bez czasów
}
SUB_EXT = (".srt", ".vtt", ".ass")  # pliki napisów, które da się wczytać do tłumaczenia


def is_subtitle(path):
    return path.lower().endswith(SUB_EXT)


def _ts(t, sep=","):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}{sep}{ms:03}"


def _ts_ass(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,120,120,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_subs(cues, path, max_chars=42, lang=None, max_lines=2):
    """Format wg rozszerzenia pliku (.srt / .vtt / .ass / .txt)."""
    max_chars = line_chars(lang, max_chars)
    fmt = os.path.splitext(path)[1].lower().lstrip(".")
    text = lambda c: wrap(c.text, max_chars, max_lines) or "…"
    with open(path, "w", encoding="utf-8") as f:
        if fmt == "vtt":
            f.write("WEBVTT\n\n")
            for c in cues:  # w WebVTT „&” i „<” mają specjalne znaczenie
                body = text(c).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                f.write(f"{_ts(c.start, '.')} --> {_ts(c.end, '.')}\n{body}\n\n")
        elif fmt == "ass":
            f.write(ASS_HEADER)
            for c in cues:  # „{…}” to w ASS znaczniki stylu, \N / \n / \h — znaki specjalne
                # „\” + niewidoczna spacja: C:\new nie zamieni się w łamanie linii
                body = text(c).replace("\\", "\\\u200b").replace("{", "(").replace("}", ")").replace("\n", "\\N")
                f.write(f"Dialogue: 0,{_ts_ass(c.start)},{_ts_ass(c.end)},Default,,0,0,0,,{body}\n")
        elif fmt == "txt":
            f.write("\n".join(c.text.strip() for c in cues if c.text.strip()) + "\n")
        else:
            for i, c in enumerate(cues, 1):
                f.write(f"{i}\n{_ts(c.start)} --> {_ts(c.end)}\n{text(c)}\n\n")


_TS = re.compile(r"(?:(\d+):)?(\d+):(\d+)[,.](\d+)")


def _parse_ts(s):
    m = _TS.search(s)
    if not m:
        raise ValueError(s)
    h, mi, sec, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(sec) + int(ms.ljust(3, "0")[:3]) / 1000


def _read_text(path):
    """UTF-8 / UTF-16 (wg BOM), a gdy to nie UTF-8 — Windows-1250/1252 (eksporty z części programów)."""
    raw = open(path, "rb").read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1250", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _read_ass(lines):
    cues, fields = [], None
    for line in lines:
        key, _, value = line.partition(":")
        if key.strip() == "Format":
            fields = [x.strip().lower() for x in value.split(",")]
        elif key.strip() == "Dialogue" and fields and "text" in fields:
            row = [x.strip() for x in value.split(",", len(fields) - 1)]
            if len(row) != len(fields):
                continue
            row = dict(zip(fields, row))
            text = re.sub(r"\{[^}]*\}", "", row["text"])  # znaczniki stylu
            text = re.sub(r"\\[Nnh]", " ", text).replace("\\​", "\\")  # zabezpieczony „\” z write_subs
            try:
                cues.append(Cue(_parse_ts(row["start"]), _parse_ts(row["end"]), " ".join(text.split())))
            except (KeyError, ValueError):
                continue
    return sorted(cues, key=lambda c: c.start)


def read_subs(path):
    """Napisy z pliku .srt / .vtt / .ass (sam tekst, bez formatowania)."""
    lines = _read_text(path).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues = _read_ass(lines) if path.lower().endswith(".ass") else _read_srt_vtt(lines, path.lower().endswith(".vtt"))
    if not cues:
        raise RuntimeError(t("srt_empty", path=path))
    return cues


def _read_srt_vtt(lines, vtt):
    import html

    cues = []
    for i, line in enumerate(lines):
        if "-->" not in line:
            continue
        a, z = line.split("-->", 1)
        try:
            start, end = _parse_ts(a), _parse_ts(z)  # w WebVTT po czasie mogą być ustawienia (align:…)
        except ValueError:
            continue
        text = []  # treść: do następnej linii z czasem (pusta linia w środku napisu nie ucina tekstu)
        for nxt in lines[i + 1:]:
            if "-->" in nxt or (vtt and not nxt.strip()):  # w WebVTT pusta linia kończy napis
                break
            text.append(nxt.strip())
        # pusta linia i numer następnego napisu (SRT; w WebVTT pusta linia już zakończyła napis, a liczba to tekst)
        while text and (not text[-1] or (not vtt and text[-1].isdigit())):
            text.pop()
        body = " ".join(x for x in text if x)
        if vtt:  # <v Jan>, <i>, <00:01.000>, &amp;
            body = html.unescape(re.sub(r"<[^>]*>", "", body)).strip()
        cues.append(Cue(start, end, body))
    return cues


# ---------------------------------------------------------------- tłumaczenie

CLAUDE_MODEL = "claude-opus-5-5"  # domyślny model Claude API

ENGINES = {
    "cli": "Claude CLI",
    "api": "Claude API",
    "codex": "Codex CLI",
    "openai": "OpenAI API",
    "ollama": "Ollama",
    "custom": "OpenAI-compatible API",
    "deepl": "DeepL",
}
# pola wymagane przez silnik (poza kluczem): model / adres serwera
ENGINE_FIELDS = {"api": ("model",), "openai": ("model",), "ollama": ("model",), "custom": ("url", "model")}
ENGINE_KEY = {"api": "anthropic", "openai": "openai", "custom": "custom", "deepl": "deepl"}
DEFAULTS = {"api_model": CLAUDE_MODEL, "openai_model": "gpt-5", "ollama_url": "http://localhost:11434/v1", "custom_url": "", "custom_model": ""}

SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["id", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["translations"],
    "additionalProperties": False,
}

SYSTEM = """You are a professional subtitle translator for video. Translate subtitle cues from {src} to {tgt}.

- Return exactly one translation for every id you receive, with the same ids.
- Each cue is timed to speech, so keep each cue's meaning in that cue. Move a word to a neighbouring cue only when {tgt} grammar requires it.
- Write natural, concise spoken {tgt} that is easy to read quickly on screen; shorten filler words if needed.
- The source is automatic speech recognition and may contain mistakes. Translate what the speaker most likely meant.
- Keep names, numbers and brand names unless the context says otherwise. No line breaks, no notes or comments."""


def _llm_lang(code):
    return LANGUAGES[code][1] if code in LANGUAGES else code


def search_path():
    """PATH + typowe miejsca instalacji CLI (npm, Homebrew…). Aplikacja uruchomiona z Findera albo menu
    aplikacji dostaje okrojony PATH (/usr/bin:/bin…), więc sam PATH by ich nie znalazł."""
    home = os.path.expanduser("~")
    extra = [] if sys.platform == "win32" else [
        "/opt/homebrew/bin", "/usr/local/bin", os.path.join(home, ".local", "bin"),
        os.path.join(home, ".npm-global", "bin"), os.path.join(home, ".bun", "bin"),
        os.path.join(home, ".volta", "bin"), "/snap/bin"]
    if sys.platform != "win32":  # nvm: bieżąca (najnowsza) wersja node
        import glob

        extra += sorted(glob.glob(os.path.join(home, ".nvm", "versions", "node", "*", "bin")), reverse=True)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    return os.pathsep.join(dict.fromkeys(parts + [d for d in extra if os.path.isdir(d)]))


def find_claude():
    """claude z PATH, a jeśli go nie ma — najnowsza kopia z aplikacji desktopowej Claude."""
    import glob
    import shutil

    exe = shutil.which("claude", path=search_path())
    if exe:
        return exe
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "bin", "claude"),
        os.path.join(home, ".claude", "local", "claude"),
    ]
    found = [c for c in candidates if os.path.isfile(c)]
    if not found:  # kopia z aplikacji desktopowej Claude
        app_dirs = {
            "win32": os.path.join(os.environ.get("APPDATA", ""), "Claude"),
            "darwin": os.path.join(home, "Library", "Application Support", "Claude"),
        }
        app = app_dirs.get(sys.platform, os.path.join(home, ".config", "Claude"))
        found = glob.glob(os.path.join(app, "claude-code", "*", "*", "claude.exe" if sys.platform == "win32" else "claude"))
    if not found:
        raise RuntimeError(t("cli_missing"))
    return max(found, key=os.path.getmtime)


def engine_setting(settings, engine, field):
    """Model / adres dla silnika: z ustawień, a gdy pusto — wartość domyślna."""
    key = f"{engine}_{field}"
    return (settings or {}).get(key) or DEFAULTS.get(key, "")


def translate(cues, src, tgt, engine, context, log, keys, settings=None, progress=lambda v: None):
    """engine: klucz z ENGINES; keys: klucze API; settings: modele / adresy (openai_model, custom_url…)."""
    log(t("translating", src=lang_name(src), tgt=lang_name(tgt), engine=ENGINES[engine], n=len(cues)))
    if engine == "deepl":
        return _translate_deepl(cues, src, tgt, context, keys.get("deepl", ""), progress)
    ask, chunk = _llm(engine, keys, settings)
    system = SYSTEM.format(src=_llm_lang(src), tgt=_llm_lang(tgt))
    return _llm_cues(cues, system, context, log, ask, chunk, progress)


SYSTEM_CORRECT = """You proofread automatic speech recognition (ASR) output that will be used as {lang} subtitles for video.

- Return exactly one text for every id you receive, with the same ids.
- Fix misheard words, names, terms and numbers, spelling, capitalization and punctuation. Use the context and the neighbouring cues to work out what the speaker most likely said.
- Keep the speaker's own wording and language: do not paraphrase, shorten, summarize, translate or censor.
- Keep each cue's words in that cue; do not move words between cues.
- If a cue is already correct, return it unchanged. No line breaks, no notes or comments."""


def correct(cues, lang, engine, context, log, keys, settings=None, progress=lambda v: None):
    """Poprawia tekst transkrypcji przez LLM (przesłyszenia, nazwy, interpunkcja). Czasy zostają bez zmian.
    Poprawka, która za bardzo odbiega od oryginału (model przepisał zdanie zamiast je poprawić), jest odrzucana."""
    import difflib

    if engine == "deepl":
        raise RuntimeError(t("correct_deepl"))
    log(t("correcting", engine=ENGINES[engine], n=len(cues)))
    ask, chunk = _llm(engine, keys, settings)
    system = SYSTEM_CORRECT.format(lang=_llm_lang(lang))
    fixed = _llm_cues(cues, system, context, log, ask, chunk, progress, task="correct")
    changed = 0
    for old, new in zip(cues, fixed):
        if new.text == old.text:
            continue
        if difflib.SequenceMatcher(None, old.text.lower(), new.text.lower()).ratio() < 0.5:
            new.text = old.text
        else:
            changed += 1
    log(t("corrected", n=changed, total=len(cues)))
    return fixed


def _llm(engine, keys, settings=None):
    """(ask(system, user) → lista {id, text}, wielkość partii) dla tłumacza LLM."""
    chunk = 80
    if engine == "api":
        import anthropic

        client = anthropic.Anthropic(api_key=keys.get("anthropic") or None)
        model = engine_setting(settings, "api", "model")
        ask = lambda system, user: _ask_api(client, model, system, user)
    elif engine == "codex":
        exe = _find_exe("codex", t("codex_missing"))
        ask = lambda system, user: _ask_codex(exe, system, user)
    elif engine in ("openai", "ollama", "custom"):
        import openai

        url = None if engine == "openai" else engine_setting(settings, engine, "url")
        model = engine_setting(settings, engine, "model")
        if not model or (engine == "custom" and not url):
            raise RuntimeError(t("llm_setup"))
        key = keys.get("openai") if engine == "openai" else (keys.get("custom") or "none")
        client = openai.OpenAI(api_key=key or None, base_url=url)
        ask = lambda system, user: _ask_openai(client, model, system, user)
        if engine != "openai":
            chunk = 25  # lokalne modele mają zwykle małe okno kontekstu
    else:
        exe = find_claude()
        ask = lambda system, user: _ask_cli(exe, system, user)
    return ask, chunk


def check_engine(engine, keys, settings=None):
    """Szybkie sprawdzenie tłumacza przed pracą (bez wywołań płatnych API). RuntimeError z opisem, co poprawić."""
    keys = keys or {}
    if engine == "cli":
        find_claude()
    elif engine == "codex":
        _find_exe("codex", t("codex_missing"))
    elif engine in ("api", "openai", "deepl") and not keys.get(ENGINE_KEY[engine]):
        raise RuntimeError(t("engine_no_key", engine=ENGINES[engine]))
    if engine in ENGINE_FIELDS and any(not engine_setting(settings, engine, f) for f in ENGINE_FIELDS[engine]):
        raise RuntimeError(t("llm_setup"))
    if engine == "ollama" and not ollama_models(engine_setting(settings, "ollama", "url")):
        raise RuntimeError(t("ollama_down"))


def _find_exe(name, missing_msg):
    import shutil

    exe = shutil.which(name, path=search_path())
    if not exe:
        raise RuntimeError(missing_msg)
    return exe


def _json_payload(text):
    """Model lokalny może dopisać coś wokół JSON-a (np. <think>…</think>) — bierzemy obiekt {…}."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def _ask_codex(exe, system, user):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        schema = os.path.join(tmp, "schema.json")
        out = os.path.join(tmp, "out.json")
        with open(schema, "w", encoding="utf-8") as f:
            json.dump(SCHEMA, f)
        proc = _run_proc(
            [exe, "exec", "-", "--output-schema", schema, "-o", out, "--skip-git-repo-check",
             "--sandbox", "read-only", "--ephemeral"],
            system + "\n\n" + user, cwd=tmp,
        )
        if proc.returncode != 0 or not os.path.exists(out):
            raise RuntimeError(t("codex_error", err=(proc.stderr or proc.stdout).strip()[-500:]))
        with open(out, encoding="utf-8") as f:
            return _json_payload(f.read())["translations"]


def _ask_openai(client, model, system, user):
    """OpenAI, Ollama, LM Studio, OpenRouter… — wszystko, co mówi API Chat Completions."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    fmt = {"type": "json_schema", "json_schema": {"name": "subtitles", "schema": SCHEMA, "strict": True}}
    try:
        resp = client.chat.completions.create(model=model, messages=messages, response_format=fmt)
    except Exception as e:
        if "response_format" not in str(e) and "json_schema" not in str(e):
            raise
        # serwer bez structured outputs: zwykły tryb JSON + schemat w poleceniu
        messages[0]["content"] += "\n\nReply with JSON only, matching this schema:\n" + json.dumps(SCHEMA)
        resp = client.chat.completions.create(model=model, messages=messages, response_format={"type": "json_object"})
    return _json_payload(resp.choices[0].message.content or "")["translations"]


def _llm_cues(cues, system, context, log, ask, chunk=80, progress=lambda v: None, task="translate"):
    """Napisy partiami do LLM (z kilkoma poprzednimi wynikami jako kontekst); brakujące id — jedna powtórka.
    task: "translate" albo "correct" — tylko opis zadania w poleceniu i komunikat o brakach."""
    done_word = "translated" if task == "translate" else "corrected"
    out = [Cue(c.start, c.end, c.text) for c in cues]

    for start in range(0, len(cues), chunk):
        check_cancel()
        progress(start / len(cues))
        batch = {i: cues[i].text for i in range(start, min(start + chunk, len(cues)))}
        if len(cues) > chunk:
            log(t("chunk", a=start + 1, b=start + len(batch)))
        prev = [out[i].text for i in range(max(0, start - 5), start)]
        intro = ""
        if context.strip():
            intro += f"Context about this video (topic, names, glossary):\n{context.strip()}\n\n"
        if prev:
            intro += f"Previous cues, already {done_word} (for context only):\n{json.dumps(prev, ensure_ascii=False)}\n\n"

        missing = dict(batch)
        for attempt in range(2):
            user = intro + f"Cues to {task}:\n" + json.dumps(
                [{"id": i, "text": t} for i, t in missing.items()], ensure_ascii=False)
            try:
                items = list(ask(system, user))
            except (ValueError, KeyError, TypeError, StopIteration) as e:  # odpowiedź nie jest oczekiwanym JSON-em
                raise RuntimeError(t("bad_response", err=type(e).__name__)) from e
            for item in items:
                tid, text = (item.get("id"), item.get("text")) if isinstance(item, dict) else (None, None)
                if tid in missing and isinstance(text, str) and text.strip():  # pusty tekst = brak odpowiedzi
                    out[tid].text = text
                    del missing[tid]
            if not missing:
                break
            if attempt == 0:
                log(t("retry_missing", n=len(missing)))
        if missing:
            log(t("untranslated" if task == "translate" else "uncorrected", n=len(missing)))
    return out


def _ask_cli(exe, system, user):
    proc = _run_proc(
        [exe, "-p", "Process the subtitle cues given on stdin, following the system prompt.",
         "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
         "--system-prompt", system, "--tools", "",
         # bez serwerów MCP, wtyczek i zapisu sesji użytkownika: start CLI ~2 s szybciej
         "--strict-mcp-config", "--no-session-persistence", "--no-chrome", "--disable-slash-commands"],
        user,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(t("cli_error", err=(proc.stderr or proc.stdout).strip()[:500]))
    if data.get("is_error"):
        msg = data.get("result", "")
        if "authenticate" in msg.lower() or "login" in msg.lower():
            msg += t("cli_login")
        raise RuntimeError(f"Claude CLI: {msg}")
    result = data.get("structured_output") or json.loads(data["result"])
    return result["translations"]


def _ask_api(client, model, system, user):
    import anthropic

    fmt = {"type": "json_schema", "schema": SCHEMA}
    messages = [{"role": "user", "content": user}]
    try:
        # pełna wersja: poziom wysiłku + automatyczny model zapasowy przy odmowie
        resp = client.beta.messages.create(
            model=model, max_tokens=16000, system=system, messages=messages,
            betas=["server-side-fallback-2026-07-01"],
            output_config={"effort": "medium", "format": fmt},
            extra_body={"fallbacks": "default"},
        )
    except anthropic.BadRequestError:
        # starszy / inny model nie obsługuje effort albo fallbacks — samo structured output
        resp = client.messages.create(model=model, max_tokens=16000, system=system, messages=messages,
                                      output_config={"format": fmt})
    if resp.stop_reason == "refusal":
        raise RuntimeError(t("refusal"))
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(t("truncated"))
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)["translations"]


def _translate_deepl(cues, src, tgt, context, key, progress=lambda v: None, chunk=50):
    import deepl

    if not key:
        raise RuntimeError(t("deepl_no_key"))
    target = LANGUAGES.get(tgt, (None, None, None))[2]
    if not target:
        raise RuntimeError(t("deepl_lang", lang=lang_name(tgt)))
    source = LANGUAGES[src][2].split("-")[0] if src in LANGUAGES and LANGUAGES[src][2] else None
    tr = deepl.Translator(key)
    out = []
    for start in range(0, len(cues), chunk):
        check_cancel()
        progress(start / len(cues))
        batch = cues[start:start + chunk]
        # kontekst nie jest tłumaczony ani liczony do limitu znaków
        near = " ".join(c.text for c in cues[max(0, start - 5):start + chunk + 5])
        ctx = "\n".join(filter(None, [context.strip(), near]))
        res = tr.translate_text([c.text for c in batch], source_lang=source, target_lang=target, context=ctx)
        out += [Cue(c.start, c.end, r.text) for c, r in zip(batch, res)]
    return out


def _cli_version(exe):
    import subprocess

    out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    m = re.search(r"\d+(\.\d+)+", out)  # „2.1.295 (Claude Code)” / „codex-cli 0.50.0”
    return m.group(0) if m else ""


def engine_info(engine, keys, settings=None):
    """Krótki opis aktualnego tłumacza do GUI."""
    no_key = f" · {t('no_key')}"
    try:
        if engine == "cli":
            return f"Claude Code CLI {_cli_version(find_claude())}".strip()
        if engine == "codex":
            return f"Codex CLI {_cli_version(_find_exe('codex', t('codex_missing')))}".strip()
    except Exception as e:
        return f"{ENGINES[engine]} — {t('unavailable')} ({e})"
    if engine == "api":
        return f"Claude API · {engine_setting(settings, 'api', 'model')}" + ("" if keys.get("anthropic") else no_key)
    if engine == "openai":
        return f"OpenAI API · {engine_setting(settings, 'openai', 'model')}" + ("" if keys.get("openai") else no_key)
    if engine in ("ollama", "custom"):
        url = engine_setting(settings, engine, "url") or "—"
        return f"{ENGINES[engine]} · {engine_setting(settings, engine, 'model') or '—'} · {url}"
    if not keys.get("deepl"):
        return "DeepL API" + no_key
    return "DeepL API " + ("Free" if keys["deepl"].endswith(":fx") else "Pro")


_OPENAI_SKIP = ("audio", "realtime", "transcribe", "tts", "image", "embedding", "moderation", "search", "whisper",
                "dall-e", "codex-mini", "computer-use")


def list_models(engine, keys, settings=None):
    """Modele dostępne dla klucza / serwera (pusta lista, gdy się nie da — pole zostaje do wpisania ręcznie)."""
    try:
        if engine == "api":
            import anthropic

            if not keys.get("anthropic"):
                return []
            client = anthropic.Anthropic(api_key=keys["anthropic"], timeout=15, max_retries=0)
            return [m.id for m in client.models.list()]  # najnowsze najpierw
        if engine == "ollama":
            return ollama_models(engine_setting(settings, "ollama", "url"))
        if engine in ("openai", "custom"):
            import openai

            url = None if engine == "openai" else engine_setting(settings, "custom", "url")
            key = keys.get("openai") if engine == "openai" else (keys.get("custom") or "none")
            if (engine == "openai" and not key) or (engine == "custom" and not url):
                return []
            ids = sorted(m.id for m in openai.OpenAI(api_key=key, base_url=url, timeout=15, max_retries=0).models.list())
            if engine == "openai":  # tylko modele czatu
                ids = [i for i in ids if i.startswith(("gpt-", "o1", "o3", "o4", "chatgpt"))
                       and not any(x in i for x in _OPENAI_SKIP)]
            return ids
    except Exception:
        pass
    return []


def ollama_models(url=DEFAULTS["ollama_url"]):
    """Modele zainstalowane w Ollamie (pusta lista, gdy Ollama nie działa)."""
    import urllib.request

    try:
        with urllib.request.urlopen(url.replace("/v1", "") + "/api/tags", timeout=2) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return []


def stt_info(model_name):
    try:
        _add_cuda_dll_paths()
        import ctranslate2

        dev = "GPU (CUDA)" if gpu_available() else "CPU"
    except Exception:
        dev = "CPU"
    return f"Whisper {model_name} · faster-whisper · {dev}"


# ---------------------------------------------------------------- konfiguracja i przetwarzanie pliku (GUI + CLI)

# SUBTITLE_GENERATOR_CONFIG: inny plik ustawień (np. do testów)
CONFIG = os.environ.get("SUBTITLE_GENERATOR_CONFIG") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
WHISPER_MODELS = ["large-v3", "large-v3-turbo", "medium"]
WHISPER_SIZES = {"large-v3": 3.09, "large-v3-turbo": 1.62, "medium": 1.53}  # GB do pobrania
WHISPER_RECOMMENDED = "large-v3-turbo"  # o połowę mniejszy i kilka razy szybszy, prawie tak dokładny
MEDIA_EXT = (".mp4", ".mov", ".mxf", ".mkv", ".avi", ".m4v", ".webm", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg")


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    """Zapis przez plik tymczasowy + os.replace — przerwany zapis nie zniszczy ustawień."""
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)


__version__ = "1.1.0"

KEYRING_SERVICE = "subtitle-generator"
OLD_KEYRING_SERVICE = "generator-napisow"  # nazwa z wersji przed 1.0
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "custom": "CUSTOM_API_KEY",
           "deepl": "DEEPL_API_KEY"}


def set_key(name, value):
    """Zapisuje klucz w systemowym magazynie haseł (Menedżer poświadczeń / Keychain / Secret Service)."""
    import keyring
    from keyring.errors import KeyringError, PasswordDeleteError

    try:
        if value:
            keyring.set_password(KEYRING_SERVICE, name, value)
        else:
            try:
                keyring.delete_password(KEYRING_SERVICE, name)
            except PasswordDeleteError:
                pass
    except KeyringError as e:
        raise RuntimeError(t("no_keyring", err=e, env=KEY_ENV[name])) from e


def _get_key(name):
    import keyring
    from keyring.errors import KeyringError

    try:
        value = keyring.get_password(KEYRING_SERVICE, name)
        if value is None and (value := keyring.get_password(OLD_KEYRING_SERVICE, name)):
            keyring.set_password(KEYRING_SERVICE, name, value)  # przenieś ze starej nazwy usługi
            keyring.delete_password(OLD_KEYRING_SERVICE, name)
        return value or ""
    except KeyringError:
        return ""


def api_keys(cfg):
    """Klucze z magazynu haseł, a gdy pusto — ze zmiennych środowiskowych.
    Klucze zapisane jawnym tekstem w config.json (starsze wersje) przenosi do magazynu."""
    if any(f"{n}_key" in cfg for n in KEY_ENV):
        for name in KEY_ENV:
            old = cfg.get(f"{name}_key")
            if old is None:
                continue
            try:
                if old:
                    set_key(name, old)
                del cfg[f"{name}_key"]
            except RuntimeError:
                pass  # brak magazynu: zostaje w pliku, dopóki nie da się przenieść
        save_config(cfg)
    return {name: _get_key(name) or os.environ.get(env, "") for name, env in KEY_ENV.items()}


@dataclass
class Options:
    language: str | None = None          # kod języka mowy / napisów; None = wykryj
    model: str = "large-v3"
    targets: tuple = ()                   # kody z LANGUAGES albo dowolne nazwy (tłumacze LLM, nie DeepL)
    engine: str = "cli"
    context: str = ""
    chars: int = 42
    lines: int = 2
    fmt: str = "srt"                      # klucz z FORMATS
    out_dir: str | None = None            # None = obok pliku źródłowego
    keys: dict | None = None
    settings: dict | None = None          # modele / adresy silników LLM (openai_model, custom_url…)
    on_exists: object = None              # plik wynikowy istnieje: f(path) → 'overwrite' | 'copy' | 'skip'
    correct: bool = False                 # poprawka transkrypcji przez LLM (silnik = engine)


# względny czas etapów: rozpoznawanie mowy, poprawka transkrypcji, jedno tłumaczenie
STT_WEIGHT, CORRECT_WEIGHT, TRANSLATE_WEIGHT = 1.0, 0.3, 0.4


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def free_name(path, reserved=()):
    """film.en.srt → film.en (2).srt → film.en (3).srt… — pierwsza wolna (i niezarezerwowana) nazwa."""
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{base} ({n}){ext}") or _norm(f"{base} ({n}){ext}") in reserved:
        n += 1
    return f"{base} ({n}){ext}"


def output_path(path, on_exists, reserved=None):
    """Ścieżka do zapisu albo None (pomiń). on_exists(path) → 'overwrite' | 'copy' | 'skip'.

    reserved: ścieżki, które zapisze już inny plik z tego samego zadania (np. film.mp4 i film.mov →
    oba chcą film.pl.srt). Takiej ścieżki nie nadpisujemy — drugi plik dostaje kopię, bez pytania."""
    reserved = set() if reserved is None else reserved
    if _norm(path) in reserved:
        out = free_name(path, reserved)
    elif not os.path.exists(path):
        out = path
    else:
        choice = on_exists(path) if on_exists else "copy"
        out = path if choice == "overwrite" else None if choice == "skip" else free_name(path, reserved)
    if out:
        reserved.add(_norm(out))
    return out


# równoległe tłumaczenia na kilka języków; lokalny model (Ollama) liczy na jednej karcie, więc po kolei
PARALLEL = {"ollama": 1}
MAX_PARALLEL = 4


def _names(path, o, src=None):
    folder = o.out_dir or os.path.dirname(os.path.abspath(path))
    name = os.path.splitext(os.path.basename(path))[0]
    if src and is_subtitle(path) and name.lower().endswith("." + src):  # film.pl.srt → film
        name = name[: -len(src) - 1]
    return folder, name


def unique_targets(targets, src=None):
    """Języki docelowe bez powtórzeń i bez kolizji nazw plików („Serbian (Latin)” i „serbian-latin”)."""
    seen, out = set(), []
    for tgt in dict.fromkeys(targets):
        suffix = file_suffix(tgt)
        if tgt != src and suffix not in seen and suffix != src:
            seen.add(suffix)
            out.append(tgt)
    return out


def plan_outputs(path, o, log, progress=lambda v, stage=None: None, reserved=None):
    """Przed jakąkolwiek pracą: decyzje o plikach, które już istnieją (pyta przez o.on_exists).

    Zwraca {"src": język źródła lub None, "out": {język: ścieżka zapisu lub None = pomiń}}.
    Przy automatycznym wykrywaniu język mowy ustalamy tylko wtedy, gdy obok leży już jakiś plik napisów."""
    media = not is_subtitle(path)
    src = o.language
    if not media and not src:
        raise RuntimeError(t("srt_needs_lang"))  # zgłaszamy od razu, przed pytaniami o inne pliki
    folder, name = _names(path, o, src)
    if media and not src and any(os.path.exists(os.path.join(folder, f"{name}.{c}.{o.fmt}")) for c in LANGUAGES):
        src = detect_language(path, o.model, log, progress)
    langs = ([src] if media and src else []) + unique_targets(o.targets, src)
    out = {}
    for lang in langs:
        check_cancel()
        target = os.path.join(folder, f"{name}.{file_suffix(lang)}.{o.fmt}")
        out[lang] = output_path(target, o.on_exists, reserved)
        if out[lang] is None:
            log(t("skipped_existing", path=target))
    return {"src": src, "out": out}


def process_file(path, o, log, progress=lambda v, stage=None: None, saved=lambda path: None, plan=None):
    """Wideo/audio → napisy (+ tłumaczenia). Plik napisów → tylko tłumaczenia. Zwraca listę zapisanych plików.

    progress(v, stage): v = postęp całego pliku 0–1 (None = etap bez procentów), stage = opis etapu."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    media = not is_subtitle(path)
    n_tr = len(unique_targets(o.targets, o.language))
    total = (STT_WEIGHT + (CORRECT_WEIGHT if o.correct else 0) if media else 0) + TRANSLATE_WEIGHT * n_tr or 1
    offset = 0.0
    if o.out_dir:
        os.makedirs(o.out_dir, exist_ok=True)  # brak folderu zgłosilibyśmy dopiero po transkrypcji

    shown = [0.0]

    def monotonic(v, label):  # postęp pliku nigdy się nie cofa
        if v is not None:
            v = shown[0] = max(shown[0], min(v, 1.0))
        progress(v, label)

    def stage(weight, label=None):
        def report(v, lbl=None):
            monotonic(None if v is None else (offset + v * weight) / total, lbl or label)
        return report

    keys = o.keys or {}
    if plan and plan["src"] and media:
        o = replace(o, language=plan["src"])  # język ustalony już przy planowaniu
    folder, name = _names(path, o, o.language)
    written = []
    decided = (plan or {}).get("out", {})

    def resolve(target_path, lang=None):
        if lang in decided:  # decyzja zapadła przed pracą
            return decided[lang]
        out = output_path(target_path, o.on_exists)
        if out is None:
            log(t("skipped_existing", path=target_path))
        return out

    def save(cues, target_path, message, lang, resolved=False):
        out = target_path if resolved else resolve(target_path)
        if out is None:
            return
        write_subs(cues, out, o.chars, lang, o.lines)
        written.append(out)
        saved(out)
        log(message(out))

    if not media:
        src = o.language
        if not src:
            raise RuntimeError(t("srt_needs_lang"))
        cues = read_subs(path)
        log(t("loaded_srt", n=len(cues)))
    elif o.language in decided and decided[o.language] is None and o.fmt != "txt" and \
            os.path.exists(existing := os.path.join(folder, f"{name}.{o.language}.{o.fmt}")):
        # transkrypcja już jest i ma zostać — tłumaczymy ją zamiast rozpoznawać mowę od nowa
        src, cues = o.language, read_subs(existing)
        log(t("using_existing", path=existing))
        offset += STT_WEIGHT
    else:
        words, src = transcribe(path, o.language, o.model, log, stage(STT_WEIGHT))
        offset += STT_WEIGHT
        if not words:
            log(t("no_speech"))
            return written
        cues = build_cues(words, o.chars, o.lines, lang=src)
        out = resolve(os.path.join(folder, f"{name}.{src}.{o.fmt}"), src)
        # poprawka tylko wtedy, gdy coś powstanie: zapis transkrypcji albo choć jedno niepominięte tłumaczenie
        if o.correct and (out or any(decided.get(tgt, True) for tgt in unique_targets(o.targets, src))):
            check_cancel()
            try:
                cues = correct(cues, src, o.engine, o.context, log, keys, o.settings,
                               stage(CORRECT_WEIGHT, t("stage_correct")))
            except Cancelled:
                raise
            except Exception as e:  # bez poprawki napisy i tak powstaną — z tekstu Whispera
                log(t("correct_failed", err=e))
            offset += CORRECT_WEIGHT
        save(cues, out, lambda out: t("saved_n", path=out, n=len(cues)), src, resolved=True)

    # o istniejące pliki tłumaczeń pytamy przed tłumaczeniem — pominięte języki nie są tłumaczone
    plan = {}
    for tgt in unique_targets(o.targets, src):
        check_cancel()
        out = resolve(os.path.join(folder, f"{name}.{file_suffix(tgt)}.{o.fmt}"), tgt)
        if out:
            plan[tgt] = out
    targets = list(plan)
    total = offset + TRANSLATE_WEIGHT * len(targets) or 1
    done = {x: 0.0 for x in targets}

    def report(tgt, v):
        done[tgt] = v
        finished = sum(1 for x in done.values() if x >= 1)
        label = (t("stage_translate", lang=lang_name(tgt)) if len(targets) == 1
                 else t("stage_translate_n", done=finished, n=len(targets)))
        monotonic(min(offset + TRANSLATE_WEIGHT * sum(done.values()), total) / total, label)

    def job(tgt):
        check_cancel()
        result = translate(cues, src, tgt, o.engine, o.context, log, keys, o.settings, lambda v: report(tgt, v))
        report(tgt, 1.0)
        return tgt, result

    failed = []
    workers = min(PARALLEL.get(o.engine, MAX_PARALLEL), len(targets)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(job, tgt) for tgt in targets]
        for future in as_completed(futures):
            try:
                tgt, translated = future.result()
            except Cancelled:
                CANCEL.set()  # zatrzymaj pozostałe tłumaczenia
                raise
            except Exception as e:  # błąd jednego języka nie przerywa pozostałych
                log(t("error", err=e))
                failed.append(e)
                continue
            save(translated, plan[tgt], lambda out: t("saved", path=out), tgt, resolved=True)
    if failed:  # błędy są już w logu; plik liczy się jako „z błędami” (CLI: kod wyjścia 1)
        raise AlreadyReported()
    progress(1.0, t("done"))
    return written
