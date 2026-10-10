"""Teksty interfejsu po polsku i angielsku. t("klucz", **parametry)."""
import locale
import os
import sys

LANG = "en"  # do wywołania set_lang()

S = {
    # --- core: rozpoznawanie mowy
    "loading_model": ("Ładuję model {model} ({dev})…", "Loading model {model} ({dev})…"),
    "downloading_model": ("Pobieram model {model} — tylko za pierwszym razem, to może potrwać kilka minut…",
                          "Downloading model {model} — first time only, this may take a few minutes…"),
    "detected": ("Język mowy: {lang} (pewność {prob:.0%}), długość {mins:.1f} min",
                 "Spoken language: {lang} (confidence {prob:.0%}), duration {mins:.1f} min"),
    "lang_mismatch": ("UWAGA: wybrano język „{chosen}”, ale w nagraniu słychać „{detected}” (pewność {prob:.0%}). "
                      "Zapisuję w języku „{detected}” — z wymuszonym złym językiem Whisper tłumaczyłby mowę zamiast ją zapisać.",
                      "WARNING: “{chosen}” was selected, but the recording sounds like “{detected}” ({prob:.0%} confidence). "
                      "Transcribing in “{detected}” — with the wrong language forced, Whisper would translate the speech "
                      "instead of transcribing it."),
    "gpu_failed": ("GPU nie zadziałało ({err}). Przełączam na CPU — będzie wolniej.",
                   "GPU failed ({err}). Falling back to CPU — this will be slower."),
    "download_failed": ("Nie udało się pobrać modelu {model}: {err}", "Couldn't download the {model} model: {err}"),
    "srt_empty": ("Nie znaleziono napisów w pliku: {path}", "No subtitles found in the file: {path}"),
    "cant_read_media": ("Nie da się odczytać dźwięku z pliku {name} — plik jest uszkodzony albo nie ma ścieżki audio.",
                        "Can't read audio from {name} — the file is damaged or has no audio track."),
    "no_speech": ("Nie rozpoznano mowy.", "No speech detected."),
    "loaded_srt": ("Wczytano {n} napisów.", "Loaded {n} subtitles."),
    "saved_n": ("Zapisano: {path} ({n} napisów)", "Saved: {path} ({n} subtitles)"),
    "saved": ("Zapisano: {path}", "Saved: {path}"),
    "srt_needs_lang": ("Dla pliku napisów wybierz jego język (nie „wykryj automatycznie”).",
                       "For a subtitle file, choose its language (not “auto-detect”)."),
    # --- core: tłumaczenie
    "translating": ("  Tłumaczę {src} → {tgt} ({engine}), {n} napisów",
                    "  Translating {src} → {tgt} ({engine}), {n} subtitles"),
    "chunk": ("    napisy {a}–{b}", "    subtitles {a}–{b}"),
    "retry_missing": ("    brakuje {n} odpowiedzi, ponawiam…", "    {n} responses missing, retrying…"),
    "untranslated": ("  UWAGA: {n} napisów zostało nieprzetłumaczonych (zostawiam oryginał).",
                     "  WARNING: {n} subtitles were not translated (original text kept)."),
    "uncorrected": ("  UWAGA: {n} napisów zostało bez poprawki (zostawiam tekst z rozpoznawania mowy).",
                    "  WARNING: {n} subtitles were not proofread (speech recognition text kept)."),
    "correcting": ("  Poprawiam transkrypcję ({engine}), {n} napisów",
                   "  Proofreading the transcript ({engine}), {n} subtitles"),
    "corrected": ("  Poprawiono {n} z {total} napisów.", "  Corrected {n} of {total} subtitles."),
    "correct_failed": ("  UWAGA: poprawka transkrypcji nie powiodła się ({err}). Zapisuję tekst z rozpoznawania mowy.",
                       "  WARNING: proofreading failed ({err}). Saving the speech recognition text."),
    "correct_deepl": ("DeepL nie poprawia transkrypcji — wybierz tłumacza LLM.",
                      "DeepL can't proofread — choose an LLM translator."),
    "cli_missing": ("Nie znaleziono Claude CLI. Zainstaluj Claude Code i zaloguj się (polecenie: claude).",
                    "Claude CLI not found. Install Claude Code and sign in (command: claude)."),
    "cli_error": ("Claude CLI zwróciło błąd: {err}", "Claude CLI returned an error: {err}"),
    "cli_login": (" — uruchom w terminalu: claude, i zaloguj się (/login).",
                  " — run `claude` in a terminal and sign in (/login)."),
    "bad_response": ("Tłumacz zwrócił odpowiedź w nieoczekiwanym formacie ({err}). Spróbuj ponownie lub wybierz inny model.",
                     "The translator returned a response in an unexpected format ({err}). Try again or choose another model."),
    "refusal": ("Claude odmówił przetłumaczenia tego fragmentu.", "Claude declined to translate this part."),
    "truncated": ("Odpowiedź Claude została ucięta (max_tokens).", "Claude's response was cut off (max_tokens)."),
    "deepl_no_key": ("Podaj klucz DeepL API.", "Enter a DeepL API key."),
    "deepl_lang": ("DeepL nie obsługuje języka „{lang}”. Użyj tłumacza Claude.",
                   "DeepL does not support “{lang}”. Use a Claude translator."),
    "no_keyring": ("Brak systemowego magazynu haseł ({err}). Ustaw zmienną środowiskową {env}.",
                   "No system keychain available ({err}). Set the {env} environment variable."),
    "no_key": ("brak klucza", "no key"),
    "codex_missing": ("Nie znaleziono Codex CLI. Zainstaluj: npm install -g @openai/codex, potem: codex login.",
                      "Codex CLI not found. Install it with: npm install -g @openai/codex, then: codex login."),
    "codex_error": ("Codex CLI zwróciło błąd: {err}", "Codex CLI returned an error: {err}"),
    "engine_no_key": ("Brak klucza dla tłumacza {engine} — wpisz go w sekcji Tłumaczenie.",
                      "No key for the {engine} translator — enter it in the Translation section."),
    "ollama_down": ("Ollama nie odpowiada albo nie ma pobranych modeli. Uruchom Ollamę i pobierz model (ollama pull …).",
                    "Ollama is not responding or has no models. Start Ollama and pull a model (ollama pull …)."),
    "llm_setup": ("Uzupełnij model (i adres serwera) w ustawieniach tłumacza.",
                  "Fill in the model (and server URL) in the translator settings."),
    "unavailable": ("niedostępne", "unavailable"),
    # --- GUI
    "title": ("Generator napisów", "Subtitle Generator"),
    "files": ("Pliki", "Files"),
    "files_empty": ("Dodaj wideo, audio albo gotowe napisy\n.srt/.vtt/.ass (tylko tłumaczenie)",
                    "Add video, audio or existing subtitles\n.srt/.vtt/.ass (translation only)"),
    "files_empty_dnd": ("Przeciągnij tutaj wideo, audio lub napisy (.srt/.vtt/.ass)\nalbo użyj przycisku poniżej",
                        "Drop video, audio or subtitle files (.srt/.vtt/.ass) here\nor use the button below"),
    "unsupported": ("Pominięto (nieobsługiwany typ pliku): {name}", "Skipped (unsupported file type): {name}"),
    "add_files": ("Dodaj pliki…", "Add files…"),
    "clear": ("Wyczyść", "Clear"),
    "choose_files": ("Wybierz pliki", "Choose files"),
    "media_types": ("Wideo / audio / napisy", "Video / audio / subtitles"),
    "all_files": ("Wszystkie pliki", "All files"),
    "stt": ("Rozpoznawanie mowy", "Speech recognition"),
    "speech_lang": ("Język mowy", "Spoken language"),
    "auto": ("Wykryj automatycznie", "Auto-detect"),
    "model": ("Model", "Model"),
    "no_model": ("Rozpoznawanie mowy (wideo i audio) wymaga jednorazowego pobrania modelu Whisper. "
                 "Bez niego możesz tłumaczyć gotowe pliki napisów.",
                 "Speech recognition (video and audio) needs a one-time download of a Whisper model. "
                 "Without it you can still translate existing subtitle files."),
    "model_missing": ("Model {model} nie jest pobrany.", "The {model} model is not downloaded."),
    "model_option": ("{model} · {gb} GB · {note}", "{model} · {gb} GB · {note}"),
    "note_large-v3-turbo": ("szybki (zalecany)", "fast (recommended)"),
    "note_large-v3": ("najdokładniejszy", "most accurate"),
    "note_medium": ("mniej dokładny", "less accurate"),
    "download": ("Pobierz", "Download"),
    "cancel": ("Anuluj", "Cancel"),
    "downloading": ("Pobieranie {model}… {done} / {total} GB", "Downloading {model}… {done} / {total} GB"),
    "model_downloaded": ("Pobrano model {model}.", "Downloaded the {model} model."),
    "download_cancelled": ("Przerwano pobieranie modelu {model} (następne pobieranie je wznowi).",
                           "Cancelled downloading {model} (the next download will resume it)."),
    "no_model_skip": ("Pominięto {name}: brak modelu rozpoznawania mowy — pobierz go w sekcji Rozpoznawanie mowy.",
                      "Skipped {name}: no speech recognition model — download one in the Speech recognition section."),
    "correct_box": ("Popraw tekst przez LLM", "Proofread with an LLM"),
    "correct_tip": ("Po rozpoznaniu mowy tłumacz z sekcji Tłumaczenie poprawia przesłyszenia, nazwy własne\n"
                    "i interpunkcję (z pomocą pola Kontekst). Czasy napisów zostają bez zmian,\n"
                    "a tłumaczenia powstają z poprawionego tekstu.",
                    "After speech recognition, the translator from the Translation section fixes misheard\n"
                    "words, names and punctuation (using the Context field). Timing stays the same,\n"
                    "and translations are made from the corrected text."),
    "correct_needs_llm": ("wymaga tłumacza LLM (nie DeepL)", "needs an LLM translator (not DeepL)"),
    "format": ("Format napisów", "Subtitle format"),
    "file_type": ("Typ pliku", "File type"),
    "log": ("Log", "Log"),
    "chars": ("Znaków w linii", "Characters per line"),
    "lines": ("Linii w napisie", "Lines per subtitle"),
    "translation": ("Tłumaczenie", "Translation"),
    "translator": ("Tłumacz", "Translator"),
    "key_anthropic": ("Klucz Anthropic", "Anthropic key"),
    "key_deepl": ("Klucz DeepL", "DeepL key"),
    "key_placeholder": ("wklej klucz", "paste key"),
    "key": ("Klucz API", "API key"),
    "key_optional": ("opcjonalnie", "optional"),
    "server_url": ("Adres serwera", "Server URL"),
    "url_placeholder": ("np. https://openrouter.ai/api/v1", "e.g. https://openrouter.ai/api/v1"),
    "ollama_local": ("Ollama (lokalnie)", "Ollama (local)"),
    "custom_api": ("Własne API (zgodne z OpenAI)", "Custom API (OpenAI-compatible)"),
    "translate_to": ("Tłumacz na", "Translate to"),
    "other_langs": ("Inne języki (nie dla DeepL), np. kataloński, śląski, esperanto",
                    "Other languages (not for DeepL), e.g. Catalan, Welsh, Esperanto"),
    "context": ("Kontekst — temat, nazwy własne, słownik (do poprawki i tłumaczenia, opcjonalnie)",
                "Context — topic, proper names, glossary (for proofreading and translation, optional)"),
    "engine": ("Silnik", "Engine"),
    "checking": ("Sprawdzam…", "Checking…"),
    "generate": ("Generuj napisy", "Generate subtitles"),
    "stop": ("Zatrzymaj", "Stop"),
    "stage_loading": ("Ładowanie modelu", "Loading model"),
    "stage_download": ("Pobieranie modelu", "Downloading model"),
    "stage_stt": ("Rozpoznawanie mowy", "Speech recognition"),
    "stage_translate": ("Tłumaczenie: {lang}", "Translating: {lang}"),
    "stage_correct": ("Poprawianie transkrypcji", "Proofreading the transcript"),
    "stage_detect": ("Wykrywanie języka", "Detecting language"),
    "stage_checking": ("Sprawdzanie plików", "Checking files"),
    "detected_short": ("Wykryty język: {lang} (pewność {prob:.0%})", "Detected language: {lang} ({prob:.0%} confidence)"),
    "using_existing": ("Używam istniejącej transkrypcji: {path}", "Using the existing transcript: {path}"),
    "stage_translate_n": ("Tłumaczenie: {done}/{n} języków", "Translating: {done}/{n} languages"),
    "skipped_existing": ("Pominięto (plik już istnieje): {path}", "Skipped (file already exists): {path}"),
    "exists_title": ("Plik już istnieje", "File already exists"),
    "exists_msg": ("Plik już istnieje:\n{path}", "This file already exists:\n{path}"),
    "overwrite": ("Nadpisz", "Overwrite"),
    "save_copy": ("Zapisz jako kopię", "Save as copy"),
    "skip": ("Pomiń", "Skip"),
    "apply_all": ("Zastosuj do wszystkich plików w tym zadaniu", "Apply to all files in this job"),
    "stopping": ("Zatrzymuję…", "Stopping…"),
    "cancelled": ("Przerwano.", "Cancelled."),
    "open_folder": ("Otwórz folder", "Open folder"),
    "working": ("Pracuję…", "Working…"),
    "add_first": ("Dodaj najpierw plik.", "Add a file first."),
    "done": ("Gotowe.", "Done."),
    "done_with_errors": ("Gotowe, z błędami ({n}): {files}", "Done, with errors ({n}): {files}"),
    "error": ("BŁĄD: {err}", "ERROR: {err}"),
}


class Msg(str):
    """Tekst komunikatu, który pamięta swój klucz i parametry — po nich GUI dobiera wygląd wpisu w logu."""

    def __new__(cls, text, key, kw):
        msg = super().__new__(cls, text)
        msg.key, msg.kw = key, kw
        return msg


def t(key, **kw):
    text = S[key][0 if LANG == "pl" else 1]
    return Msg(text.format(**kw) if kw else text, key, kw)


UI_LANGS = ("pl", "en")


def set_lang(lang):
    """lang: wybór użytkownika ('pl' / 'en'); bez wyboru — język systemu, a gdy go nie obsługujemy — angielski."""
    global LANG
    LANG = lang if lang in UI_LANGS else default_lang()


def default_lang():
    lang = system_lang()
    return lang if lang in UI_LANGS else "en"


def system_lang():
    """Język interfejsu systemu jako kod ('pl', 'de'…) albo '' — nie format regionalny (daty, liczby)."""
    try:
        if sys.platform == "win32":
            import ctypes

            return _code(locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), ""))
        if sys.platform == "darwin":  # aplikacja uruchomiona z Findera nie dostaje zmiennej LANG
            import subprocess

            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True,
                                 timeout=3).stdout  # ( "pl-PL", "en-US" )
            first = out.replace("(", " ").replace('"', " ").replace(",", " ").split()
            if first:
                return _code(first[0])
    except Exception:
        pass
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):  # kolejność jak w gettext
        if os.environ.get(var):
            return _code(os.environ[var].split(":")[0])
    return _code(locale.getlocale()[0] or "")


def _code(name):
    """'pl_PL.UTF-8' / 'pl-PL' / 'Polish_Poland' → 'pl'."""
    name = name.strip().lower()
    if name.startswith("polish"):
        return "pl"
    if name.startswith("english"):
        return "en"
    return name.replace("-", "_").split("_")[0].split(".")[0] if name not in ("c", "posix") else ""
