"""Generator napisów: transkrypcja (faster-whisper), podział na napisy, SRT i tłumaczenie (Claude CLI / Claude API / DeepL)."""
import json
import os
import re
import sys
import textwrap
import threading
from dataclasses import dataclass

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


def check_cancel():
    if CANCEL.is_set():
        raise Cancelled()


def _run_proc(cmd, input_text, cwd=None):
    """subprocess.run, który da się przerwać przyciskiem Stop (zabija proces)."""
    import subprocess

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", cwd=cwd,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    pending = input_text
    while True:
        try:
            out, err = proc.communicate(pending, timeout=0.3)
            return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
        except subprocess.TimeoutExpired:
            pending = None  # stdin wysłane przy pierwszym wywołaniu
            if CANCEL.is_set():
                proc.kill()
                proc.communicate()
                raise Cancelled()


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


def _run_whisper(path, language, model_name, device, log, progress):
    from faster_whisper import WhisperModel

    compute = "float16" if device == "cuda" else "int8"
    dev = "GPU" if device == "cuda" else "CPU"
    log(t("loading_model" if _model_cached(model_name) else "downloading_model", model=model_name, dev=dev))
    model = WhisperModel(model_name, device=device, compute_type=compute)
    from faster_whisper import decode_audio

    audio = decode_audio(path)
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
            progress(min(seg.end / info.duration, 1.0))
    return words, info.language


def _model_cached(model_name):
    try:
        from faster_whisper.utils import _MODELS
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache(_MODELS.get(model_name, model_name), "model.bin"), str)
    except Exception:
        return False


def transcribe(path, language, model_name, log, progress):
    """Zwraca (lista słów z czasami, wykryty język). Najpierw GPU, w razie błędu CPU."""
    _add_cuda_dll_paths()
    try:
        return _run_whisper(path, language, model_name, "cuda", log, progress)
    except Cancelled:
        raise
    except Exception as e:  # brak CUDA/cuDNN, nieobsługiwana karta itp.
        if not any(w in str(e).lower() for w in ("cuda", "cublas", "cudnn", "gpu", "device", "dll", ".so")):
            raise  # np. uszkodzony plik — CPU nic tu nie pomoże
        log(t("gpu_failed", err=e))
        return _run_whisper(path, language, model_name, "cpu", log, progress)


# ---------------------------------------------------------------- podział na napisy

SENTENCE_END = (".", "?", "!", "…")
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


def build_cues(words, max_chars=42, max_lines=2, max_dur=6.0, max_gap=0.7):
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
                            if cur[k].word.strip().endswith(",")
                            or (k + 1 < len(cur) and cur[k + 1].word.strip().lower() in CONJ)), None)
                flush(cut if too_long else None)
            elif (len(_join(cur)) >= soft
                  and (cur[-1].word.strip().endswith((",", ";", ":", "–", "-"))
                       or w.word.strip().lower() in CONJ)
                  and not sentence_fits(i)):
                flush()  # naturalna pauza w długim zdaniu
        cur.append(w)
        if _sentence_end(w) and len(_join(cur)) >= 12:
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


def wrap(text, max_chars=42):
    """Dzieli tekst na 2 linie: równe długości, cięcie po przecinku, bez jednoliterowych słów na końcu."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    spaces = [m.start() for m in re.finditer(" ", text)]
    if len(text) <= 2 * max_chars + 5 and spaces:
        best = min(spaces, key=lambda i: _break_cost(text, i, max_chars))
        return text[:best] + "\n" + text[best + 1:]
    return "\n".join(textwrap.wrap(text, max_chars))


# ---------------------------------------------------------------- SRT

def _ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(cues, path, max_chars=42):
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            f.write(f"{i}\n{_ts(c.start)} --> {_ts(c.end)}\n{wrap(c.text, max_chars)}\n\n")


def _parse_ts(s):
    h, m, rest = s.strip().replace(".", ",").split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def read_srt(path):
    with open(path, encoding="utf-8-sig") as f:
        blocks = re.split(r"\n\s*\n", f.read().replace("\r\n", "\n").strip())
    cues = []
    for b in blocks:
        lines = b.strip().split("\n")
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue
        a, z = lines[idx].split("-->")
        cues.append(Cue(_parse_ts(a), _parse_ts(z.split()[0]), " ".join(lines[idx + 1:]).strip()))
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


def find_claude():
    """claude z PATH, a jeśli go nie ma — najnowsza kopia z aplikacji desktopowej Claude."""
    import glob
    import shutil

    exe = shutil.which("claude")
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


def translate(cues, src, tgt, engine, context, log, keys, settings=None):
    """engine: klucz z ENGINES; keys: klucze API; settings: modele / adresy (openai_model, custom_url…)."""
    log(t("translating", src=lang_name(src), tgt=lang_name(tgt), engine=ENGINES[engine], n=len(cues)))
    chunk = 80
    if engine == "deepl":
        return _translate_deepl(cues, src, tgt, context, keys.get("deepl", ""))
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
    return _translate_llm(cues, src, tgt, context, log, ask, chunk)


def _find_exe(name, missing_msg):
    import shutil

    exe = shutil.which(name)
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


def _translate_llm(cues, src, tgt, context, log, ask, chunk=80):
    system = SYSTEM.format(src=_llm_lang(src), tgt=_llm_lang(tgt))
    out = [Cue(c.start, c.end, c.text) for c in cues]

    for start in range(0, len(cues), chunk):
        check_cancel()
        batch = {i: cues[i].text for i in range(start, min(start + chunk, len(cues)))}
        if len(cues) > chunk:
            log(t("chunk", a=start + 1, b=start + len(batch)))
        prev = [out[i].text for i in range(max(0, start - 5), start)]
        intro = ""
        if context.strip():
            intro += f"Context about this video (topic, names, glossary):\n{context.strip()}\n\n"
        if prev:
            intro += f"Previous cues, already translated (for context only):\n{json.dumps(prev, ensure_ascii=False)}\n\n"

        missing = dict(batch)
        for attempt in range(2):
            user = intro + "Cues to translate:\n" + json.dumps(
                [{"id": i, "text": t} for i, t in missing.items()], ensure_ascii=False)
            for item in ask(system, user):
                if item["id"] in missing:
                    out[item["id"]].text = item["text"]
                    del missing[item["id"]]
            if not missing:
                break
            log(t("retry_missing", n=len(missing)))
        if missing:
            log(t("untranslated", n=len(missing)))
    return out


def _ask_cli(exe, system, user):
    proc = _run_proc(
        [exe, "-p", "Translate the subtitle cues given on stdin, following the system prompt.",
         "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
         "--system-prompt", system, "--tools", ""],
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


def _translate_deepl(cues, src, tgt, context, key, chunk=50):
    import deepl

    if not key:
        raise RuntimeError(t("deepl_no_key"))
    target = LANGUAGES.get(tgt, (None, None, None))[2]
    if not target:
        raise RuntimeError(t("deepl_lang", lang=lang_name(tgt)))
    source = src.upper() if src in LANGUAGES and LANGUAGES[src][2] else None
    tr = deepl.Translator(key)
    out = []
    for start in range(0, len(cues), chunk):
        check_cancel()
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

        dev = "GPU (CUDA)" if ctranslate2.get_cuda_device_count() > 0 else "CPU"
    except Exception:
        dev = "CPU"
    return f"Whisper {model_name} · faster-whisper · {dev}"


# ---------------------------------------------------------------- konfiguracja i przetwarzanie pliku (GUI + CLI)

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
WHISPER_MODELS = ["large-v3", "large-v3-turbo", "medium"]
MEDIA_EXT = (".mp4", ".mov", ".mxf", ".mkv", ".avi", ".m4v", ".webm", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg")


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


__version__ = "1.0.0"

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
    targets: tuple = ()                   # kody z LANGUAGES albo dowolne nazwy (tylko Claude)
    engine: str = "cli"
    context: str = ""
    chars: int = 42
    lines: int = 2
    out_dir: str | None = None            # None = obok pliku źródłowego
    keys: dict | None = None
    settings: dict | None = None          # modele / adresy silników LLM (openai_model, custom_url…)


def process_file(path, o, log, progress=lambda v: None, saved=lambda path: None):
    """Wideo/audio → SRT (+ tłumaczenia). Plik .srt → tylko tłumaczenia. Zwraca listę zapisanych plików."""
    keys = o.keys or {}
    folder = o.out_dir or os.path.dirname(os.path.abspath(path))
    name = os.path.splitext(os.path.basename(path))[0]
    written = []

    if path.lower().endswith(".srt"):
        src = o.language
        if not src:
            raise RuntimeError(t("srt_needs_lang"))
        if name.lower().endswith("." + src):  # film.pl.srt → film
            name = name[: -len(src) - 1]
        cues = read_srt(path)
        log(t("loaded_srt", n=len(cues)))
    else:
        words, src = transcribe(path, o.language, o.model, log, progress)
        if not words:
            log(t("no_speech"))
            return written
        cues = build_cues(words, o.chars, o.lines)
        out = os.path.join(folder, f"{name}.{src}.srt")
        write_srt(cues, out, o.chars)
        written.append(out)
        saved(out)
        log(t("saved_n", path=out, n=len(cues)))

    for tgt in o.targets:
        if tgt == src:
            continue
        check_cancel()
        translated = translate(cues, src, tgt, o.engine, o.context, log, keys, o.settings)
        out = os.path.join(folder, f"{name}.{file_suffix(tgt)}.srt")
        write_srt(translated, out, o.chars)
        written.append(out)
        saved(out)
        log(t("saved", path=out))
    progress(1.0)
    return written
