"""Teksty interfejsu po polsku i angielsku. t("klucz", **parametry)."""
import locale
import os

LANG = "pl"

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
    "no_speech": ("Nie rozpoznano mowy.", "No speech detected."),
    "loaded_srt": ("Wczytano {n} napisów.", "Loaded {n} subtitles."),
    "saved_n": ("Zapisano: {path} ({n} napisów)", "Saved: {path} ({n} subtitles)"),
    "saved": ("Zapisano: {path}", "Saved: {path}"),
    "srt_needs_lang": ("Dla pliku .srt wybierz język napisów (nie „wykryj automatycznie”).",
                       "For an .srt file, choose the subtitle language (not “auto-detect”)."),
    # --- core: tłumaczenie
    "translating": ("  Tłumaczę {src} → {tgt} ({engine}), {n} napisów",
                    "  Translating {src} → {tgt} ({engine}), {n} subtitles"),
    "chunk": ("    napisy {a}–{b}", "    subtitles {a}–{b}"),
    "retry_missing": ("    brakuje {n} tłumaczeń, ponawiam…", "    {n} translations missing, retrying…"),
    "untranslated": ("  UWAGA: {n} napisów zostało nieprzetłumaczonych (zostawiam oryginał).",
                     "  WARNING: {n} subtitles were not translated (original text kept)."),
    "cli_missing": ("Nie znaleziono Claude CLI. Zainstaluj Claude Code i zaloguj się (polecenie: claude).",
                    "Claude CLI not found. Install Claude Code and sign in (command: claude)."),
    "cli_error": ("Claude CLI zwróciło błąd: {err}", "Claude CLI returned an error: {err}"),
    "cli_login": (" — uruchom w terminalu: claude, i zaloguj się (/login).",
                  " — run `claude` in a terminal and sign in (/login)."),
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
    "llm_setup": ("Uzupełnij model (i adres serwera) w ustawieniach tłumacza.",
                  "Fill in the model (and server URL) in the translator settings."),
    "unavailable": ("niedostępne", "unavailable"),
    # --- GUI
    "title": ("Generator napisów", "Subtitle Generator"),
    "files": ("Pliki", "Files"),
    "files_empty": ("Dodaj wideo, audio albo gotowy plik .srt (tylko tłumaczenie)",
                    "Add video, audio or an existing .srt file (translation only)"),
    "files_empty_dnd": ("Przeciągnij tutaj wideo, audio lub plik .srt — albo użyj przycisku poniżej",
                        "Drop video, audio or .srt files here — or use the button below"),
    "unsupported": ("Pominięto (nieobsługiwany typ pliku): {name}", "Skipped (unsupported file type): {name}"),
    "add_files": ("Dodaj pliki…", "Add files…"),
    "clear": ("Wyczyść", "Clear"),
    "choose_files": ("Wybierz pliki", "Choose files"),
    "media_types": ("Wideo / audio / SRT", "Video / audio / SRT"),
    "all_files": ("Wszystkie pliki", "All files"),
    "stt": ("Rozpoznawanie mowy", "Speech recognition"),
    "speech_lang": ("Język mowy", "Spoken language"),
    "auto": ("Wykryj automatycznie", "Auto-detect"),
    "model": ("Model", "Model"),
    "format": ("Format napisów", "Subtitle format"),
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
    "context": ("Kontekst dla tłumacza — temat, nazwy własne, słownik (opcjonalnie)",
                "Context for the translator — topic, proper names, glossary (optional)"),
    "engine": ("Silnik", "Engine"),
    "checking": ("Sprawdzam…", "Checking…"),
    "generate": ("Generuj napisy", "Generate subtitles"),
    "stop": ("Zatrzymaj", "Stop"),
    "stage_loading": ("Ładowanie modelu", "Loading model"),
    "stage_download": ("Pobieranie modelu", "Downloading model"),
    "stage_stt": ("Rozpoznawanie mowy", "Speech recognition"),
    "stage_translate": ("Tłumaczenie: {lang}", "Translating: {lang}"),
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
    "error": ("BŁĄD: {err}", "ERROR: {err}"),
}


def t(key, **kw):
    text = S[key][0 if LANG == "pl" else 1]
    return text.format(**kw) if kw else text


def set_lang(lang):
    global LANG
    LANG = lang if lang in ("pl", "en") else default_lang()


def default_lang():
    loc = os.environ.get("LANG") or (locale.getlocale()[0] or "")
    return "pl" if loc.lower().startswith(("pl", "polish")) else "en"
