"""Subtitle Generator / Generator napisów — command line."""
import argparse
import json
import sys

import core
import i18n
from i18n import t

i18n.S.update({
    "cli_desc": ("Wideo/audio → napisy SRT / WebVTT / ASS / TXT (+ tłumaczenia).",
                 "Video/audio → SRT / WebVTT / ASS / TXT subtitles (+ translations)."),
    "cli_examples": (
        "Przykłady:\n"
        "  generator-cli film.mp4                                  napisy w języku mowy (wykrywany)\n"
        "  generator-cli film.mp4 -l pl -t en,de                   PL + tłumaczenia EN i DE\n"
        "  generator-cli film.pl.srt -l pl -t francuski -e deepl   tylko tłumaczenie gotowego SRT",
        "Examples:\n"
        "  generator-cli video.mp4                                 subtitles in the spoken language (detected)\n"
        "  generator-cli video.mp4 -l en -t pl,de                  EN + PL and DE translations\n"
        "  generator-cli video.en.srt -l en -t french -e deepl     translate an existing SRT only"),
    "a_files": ("pliki wideo/audio lub napisy .srt/.vtt/.ass/.sub/.txt", "video/audio or .srt/.vtt/.ass/.sub/.txt subtitle files"),
    "a_lang": ("język mowy / napisów (kod lub nazwa), domyślnie auto",
               "spoken / subtitle language (code or name), default: auto"),
    "a_translate": ("języki docelowe po przecinku, np. en,de,kataloński",
                    "target languages, comma-separated, e.g. pl,de,catalan"),
    "a_engine": ("tłumacz: cli, api (Claude API), codex, openai, ollama, custom (API zgodne z OpenAI), deepl",
                 "translator: cli, api (Claude API), codex, openai, ollama, custom (OpenAI-compatible API), deepl"),
    "a_llm_model": ("model dla api / openai / ollama / custom", "model for api / openai / ollama / custom"),
    "a_llm_url": ("adres serwera dla ollama / custom", "server URL for ollama / custom"),
    "a_model": ("model Whisper", "Whisper model"),
    "a_context": ("kontekst dla tłumacza (temat, nazwy, słownik)", "context for the translator (topic, names, glossary)"),
    "a_out": ("folder wyjściowy (domyślnie obok pliku)", "output folder (default: next to the source file)"),
    "a_format": ("format zapisu (srt)", "output format (srt)"),
    "a_correct": ("popraw transkrypcję tłumaczem LLM z -e (przesłyszenia, nazwy, interpunkcja)",
                  "proofread the transcript with the -e LLM translator (misheard words, names, punctuation)"),
    "a_chars": ("maks. znaków w linii (42)", "max characters per line (42)"),
    "a_lines": ("maks. linii w napisie (2)", "max lines per subtitle (2)"),
    "a_overwrite": ("nadpisuj istniejące pliki (domyślnie: zapis jako kopia, np. film.en (2).srt)",
                    "overwrite existing files (default: save as a copy, e.g. video.en (2).srt)"),
    "a_download": ("pobierz brakujący model Whisper bez pytania (np. w skryptach)",
                   "download a missing Whisper model without asking (e.g. in scripts)"),
    "model_ask": ("Model rozpoznawania mowy {model} ({gb} GB) nie jest pobrany. Pobrać teraz? [t/N] ",
                  "The {model} speech recognition model ({gb} GB) is not downloaded. Download it now? [y/N] "),
    "model_skip_cli": ("Model {model} nie jest pobrany — pomijam pliki wideo i audio ({n}). "
                       "Aby go pobrać, uruchom program w terminalu albo z opcją --download-model.",
                       "The {model} model is not downloaded — skipping video and audio files ({n}). "
                       "To download it, run the program in a terminal or with --download-model."),
    "a_jobs": ("ile partii jednego tłumaczenia wysyłać naraz (1)", "how many parts of one translation to send at once (1)"),
    "a_fps": ("klatki/s dla napisów MicroDVD (domyślnie z pliku albo 23.976)",
              "frames per second for MicroDVD subtitles (default: from the file, otherwise 23.976)"),
    "a_json": ("komunikaty i postęp jako JSON, jeden obiekt na linię (dla innych programów)",
               "messages and progress as JSON, one object per line (for other programs)"),
    "a_convert": ("zapisz plik napisów w formacie z -f (np. MicroDVD → SRT), także bez tłumaczenia",
                  "save the subtitle file in the -f format (e.g. MicroDVD → SRT), also without translating"),
    "a_list": ("pokaż obsługiwane języki", "list supported languages"),
    "a_ui": ("język komunikatów: pl lub en", "message language: pl or en"),
    "translator_is": ("Tłumacz: {info}", "Translator: {info}"),
    "claude_only": ("(bez DeepL)", "(not DeepL)"),
})


MAX_JOBS = 16  # górna granica --jobs (każda partia to osobny proces / zapytanie)


def main():
    for stream in (sys.stdout, sys.stderr):  # konsola Windows (cp1250) nie zna „→” itp.
        stream.reconfigure(errors="replace")
    cfg = core.load_config()
    lang_arg = next((sys.argv[i + 1] for i, x in enumerate(sys.argv[:-1]) if x == "--ui-lang"), None)
    i18n.set_lang(lang_arg or cfg.get("ui_lang"))

    p = argparse.ArgumentParser(prog="generator-cli", description=t("cli_desc"), epilog=t("cli_examples"),
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="*", help=t("a_files"))
    p.add_argument("-l", "--language", default="auto", help=t("a_lang"))
    p.add_argument("-t", "--translate", default="", help=t("a_translate"))
    p.add_argument("-e", "--engine", choices=list(core.ENGINES), default=None, help=t("a_engine"))
    p.add_argument("-m", "--model", choices=core.WHISPER_MODELS, default="large-v3", help=t("a_model"))
    p.add_argument("--download-model", action="store_true", help=t("a_download"))
    p.add_argument("--llm-model", help=t("a_llm_model"))
    p.add_argument("--llm-url", help=t("a_llm_url"))
    p.add_argument("-c", "--context", default="", help=t("a_context"))
    p.add_argument("-o", "--out-dir", help=t("a_out"))
    p.add_argument("-f", "--format", choices=list(core.FORMATS), default="srt", help=t("a_format"))
    p.add_argument("--correct", action="store_true", help=t("a_correct"))
    p.add_argument("--chars", type=int, default=42, help=t("a_chars"))
    p.add_argument("--lines", type=int, default=2, help=t("a_lines"))
    p.add_argument("--overwrite", action="store_true", help=t("a_overwrite"))
    p.add_argument("--jobs", type=int, default=1, help=t("a_jobs"))
    p.add_argument("--fps", type=float, help=t("a_fps"))
    p.add_argument("--convert", action="store_true", help=t("a_convert"))
    p.add_argument("--json", action="store_true", help=t("a_json"))
    p.add_argument("--list-languages", action="store_true", help=t("a_list"))
    p.add_argument("--ui-lang", choices=["pl", "en"], help=t("a_ui"))
    a = p.parse_args()

    if a.list_languages:
        for code, (pl, en, dl) in core.LANGUAGES.items():
            print(f"{code:4} {pl:14} {en:14} {'DeepL' if dl else t('claude_only')}")
        return 0
    if not a.files:
        p.print_usage()
        return 2

    lang = None if a.language.lower() in ("auto", "") else core.resolve_language(a.language)
    targets = tuple(core.resolve_language(x) for x in a.translate.split(",") if x.strip())
    engine = a.engine or cfg.get("engine", "cli")
    settings = dict(cfg)
    if a.llm_model:
        settings[f"{engine}_model"] = a.llm_model
    if a.llm_url:
        settings[f"{engine}_url"] = a.llm_url
    opts = core.Options(language=lang, model=a.model, targets=targets, engine=engine, context=a.context,
                        chars=a.chars, lines=a.lines, fmt=a.format, out_dir=a.out_dir, keys=core.api_keys(cfg),
                        settings=settings, on_exists=(lambda p: "overwrite") if a.overwrite else None,
                        correct=a.correct, jobs=min(max(1, a.jobs), MAX_JOBS), fps=a.fps,
                        convert=a.convert)

    if a.json:  # jeden obiekt JSON na linię — dla programów (np. dodatku do Stremio)
        emit = lambda **kw: print(json.dumps(kw, ensure_ascii=False), flush=True)
        log = lambda msg: emit(**{"error" if getattr(msg, "key", "") == "error" else "log": str(msg)})
        error = lambda msg: emit(error=str(msg))
        progress = lambda v, stage=None: v is not None and emit(progress=round(v, 3), stage=str(stage or ""))
        saved = lambda path: emit(saved=path)
    else:
        log, progress, saved = print, _progress, lambda path: None
        error = lambda msg: print(msg, file=sys.stderr)
    nl = "" if a.json else "\n"  # w terminalu błąd zaczyna nową linię po pasku postępu

    if a.correct and engine == "deepl":
        error(t("error", err=t("correct_deepl")))
        return 1
    if targets or a.correct:
        try:  # niedostępny tłumacz zgłaszamy przed transkrypcją
            core.check_engine(opts.engine, opts.keys, settings)
        except RuntimeError as e:
            error(t("error", err=e))
            return 1
        log(t("translator_is", info=core.engine_info(opts.engine, opts.keys, settings)))
    failed, files = 0, list(a.files)
    media = [f for f in files if not core.is_subtitle(f)]
    if media and not core.model_cached(a.model) and not _get_model(a.model, a.download_model, log, error, nl):
        # bez modelu: pliki wideo/audio pomijamy, pliki napisów tłumaczymy
        error(t("model_skip_cli", model=a.model, n=len(media)))
        files = [f for f in files if core.is_subtitle(f)]
        failed += len(media)
    for path in files:
        log(f"=== {path}")
        try:
            core.process_file(path, opts, log, progress, saved)
        except core.AlreadyReported:  # błędy tłumaczeń są już wypisane
            failed += 1
        except Exception as e:
            error(nl + t("error", err=e))
            failed += 1
    return 1 if failed else 0


def _get_model(model, without_asking, log=print, error=print, nl="\n"):
    """Brak modelu Whisper: pobiera go po zgodzie (pytanie w terminalu) albo z opcją --download-model.
    Bez terminala (skrypt, potok) i bez tej opcji nic nie pobiera. Zwraca True, gdy model jest gotowy."""
    if not without_asking:
        if not sys.stdin.isatty():
            return False
        gb = i18n.decimal(core.WHISPER_SIZES.get(model, 0))
        try:
            answer = input(t("model_ask", model=model, gb=gb))
        except EOFError:
            return False
        if answer.strip().lower() not in ("t", "tak", "y", "yes"):
            return False

    def progress(done, total):
        if sys.stdout.isatty() and total:
            text = t("downloading", model=model, done=i18n.decimal(done / 1e9), total=i18n.decimal(total / 1e9))
            print(f"\r  {text} {done / total:4.0%}   ", end="", flush=True)

    try:
        core.download_model(model, progress)
    except RuntimeError as e:
        error(nl + t("error", err=e))
        return False
    log(nl + t("model_downloaded", model=model))
    return True


def _progress(v, stage=None):
    if sys.stdout.isatty() and v is not None:
        print(f"\r  {stage or ''}: {v:5.0%}   ", end="\n" if v >= 1 else "", flush=True)


if __name__ == "__main__":
    sys.exit(main())
