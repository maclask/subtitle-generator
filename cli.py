"""Subtitle Generator / Generator napisów — command line."""
import argparse
import sys

import core
import i18n
from i18n import t

i18n.S.update({
    "cli_desc": ("Wideo/audio → napisy SRT (+ tłumaczenia).", "Video/audio → SRT subtitles (+ translations)."),
    "cli_examples": (
        "Przykłady:\n"
        "  generator-cli film.mp4                                  napisy w języku mowy (wykrywany)\n"
        "  generator-cli film.mp4 -l pl -t en,de                   PL + tłumaczenia EN i DE\n"
        "  generator-cli film.pl.srt -l pl -t francuski -e deepl   tylko tłumaczenie gotowego SRT",
        "Examples:\n"
        "  generator-cli video.mp4                                 subtitles in the spoken language (detected)\n"
        "  generator-cli video.mp4 -l en -t pl,de                  EN + PL and DE translations\n"
        "  generator-cli video.en.srt -l en -t french -e deepl     translate an existing SRT only"),
    "a_files": ("pliki wideo/audio lub .srt", "video/audio or .srt files"),
    "a_lang": ("język mowy / napisów (kod lub nazwa), domyślnie auto",
               "spoken / subtitle language (code or name), default: auto"),
    "a_translate": ("języki docelowe po przecinku, np. en,de,kataloński",
                    "target languages, comma-separated, e.g. pl,de,catalan"),
    "a_engine": ("tłumacz: cli, api (Claude API), codex, openai, ollama, custom (API zgodne z OpenAI), deepl",
                 "translator: cli, api (Claude API), codex, openai, ollama, custom (OpenAI-compatible API), deepl"),
    "a_llm_model": ("model dla openai / ollama / custom", "model for openai / ollama / custom"),
    "a_llm_url": ("adres serwera dla ollama / custom", "server URL for ollama / custom"),
    "a_model": ("model Whisper", "Whisper model"),
    "a_context": ("kontekst dla tłumacza (temat, nazwy, słownik)", "context for the translator (topic, names, glossary)"),
    "a_out": ("folder wyjściowy (domyślnie obok pliku)", "output folder (default: next to the source file)"),
    "a_chars": ("maks. znaków w linii (42)", "max characters per line (42)"),
    "a_lines": ("maks. linii w napisie (2)", "max lines per subtitle (2)"),
    "a_list": ("pokaż obsługiwane języki", "list supported languages"),
    "a_ui": ("język komunikatów: pl lub en", "message language: pl or en"),
    "translator_is": ("Tłumacz: {info}", "Translator: {info}"),
    "progress": ("  rozpoznawanie mowy: {v:5.0%}", "  speech recognition: {v:5.0%}"),
    "claude_only": ("(tylko Claude)", "(Claude only)"),
})


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
    p.add_argument("--llm-model", help=t("a_llm_model"))
    p.add_argument("--llm-url", help=t("a_llm_url"))
    p.add_argument("-c", "--context", default="", help=t("a_context"))
    p.add_argument("-o", "--out-dir", help=t("a_out"))
    p.add_argument("--chars", type=int, default=42, help=t("a_chars"))
    p.add_argument("--lines", type=int, default=2, help=t("a_lines"))
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
                        chars=a.chars, lines=a.lines, out_dir=a.out_dir, keys=core.api_keys(cfg),
                        settings=settings)

    if targets:
        print(t("translator_is", info=core.engine_info(opts.engine, opts.keys, settings)))
    failed = 0
    for path in a.files:
        print(f"=== {path}")
        try:
            core.process_file(path, opts, print, _progress)
        except Exception as e:
            print("\n" + t("error", err=e), file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def _progress(v):
    if sys.stdout.isatty():
        print("\r" + t("progress", v=v), end="\n" if v >= 1 else "", flush=True)


if __name__ == "__main__":
    sys.exit(main())
