# Subtitle Generator — map for Claude sessions

Desktop app + CLI: video/audio → subtitles (faster-whisper), optional LLM proofreading, translation
(Claude CLI/API, Codex CLI, OpenAI, Ollama, custom OpenAI-compatible, DeepL). Python 3.10–3.13,
GUI in customtkinter. The user communicates in Polish; code comments and docstrings are in Polish,
README exists in EN (`README.md`) and PL (`README.pl.md`) — keep both in sync, formal tone.

## Environment gotchas (Windows dev machine)

- `python` on PATH is **Python 2** — always use `.venv/Scripts/python.exe`, with `PYTHONUTF8=1`.
- Bash heredocs in this harness can mangle backslashes (`\\n`). For multi-line Python patch scripts,
  write the script with the Write tool into the scratchpad and run it.
- Display scaling is 175%: Tk reports screen size already in logical units; CTk `geometry()`/`minsize()`
  take logical units; `winfo_reqwidth/height` return physical pixels (divide by
  `ctk.ScalingTracker.get_window_scaling`).
- Test isolation: `SUBTITLE_GENERATOR_CONFIG=<tmp json>` (settings file), `HF_HUB_CACHE=<tmp dir>`
  (Whisper model cache). Never touch the user's `config.json` or HF cache in tests. User has
  `large-v3` downloaded.
- GUI checks: script that builds `gui.App()`, pushes fake entries via `app.q.put((kind, val))`,
  then `app.attributes("-topmost", True)` and `PIL.ImageGrab.grab(window bbox)` → Read the PNG.
  Always topmost + on-screen geometry, otherwise the grab captures the user's desktop.
- Claude CLI is installed and logged in — fine for small real LLM tests (`core.correct`, `translate`).

## Files

| File | Role |
|---|---|
| `core.py` (~1430 lines) | all logic, no Tk; shared by GUI and CLI |
| `gui.py` (~1260) | customtkinter app (`App`), worker thread + queue |
| `cli.py` (~170) | argparse front end; adds its own strings to `i18n.S` |
| `i18n.py` (~235) | `S` dict of `key: (pl, en)`, `t()`, language detection |
| `shortcuts.py` | creates launchers/shortcuts (run by setup scripts) |
| `tools/make_icons.py` | regenerates `assets/icon.{png,ico,icns}` (each size drawn separately) |
| `tools/build_release.py` | builds 6 archives into `dist/` from **HEAD** (not working tree) |
| `setup.bat` / `setup.sh` | create `.venv`, install `requirements*.txt`, run `shortcuts.py` |

## core.py sections (in file order)

- `LANGUAGES` {code: (pl name, en name, DeepL code|None)}, `lang_name`, `resolve_language`, `file_suffix`.
- Cancellation: global `CANCEL` Event, `check_cancel()`, `Cancelled`, `AlreadyReported`;
  `_ACTIVE` subprocess set + `_kill_tree`, `kill_active()` (window close), `_run_proc` (cancellable subprocess).
- Whisper: `_load_model` (never downloads: `local_files_only=True`, raises `model_not_downloaded`),
  `_run_whisper`, `transcribe`, `detect_language`, GPU→CPU fallback `_on_gpu_or_cpu`.
  Model cache: `WHISPER_REPOS`, `_model_dir`, `model_cached` (glob `snapshots/*/model.bin`, no
  faster_whisper import), `download_model` (subprocess, progress from `_downloaded_bytes`, cancel kills it).
- Segmentation: `build_cues` (sentence/clause aware), `fix_timing`, `wrap` (balanced lines, Polish typography).
- Formats: `FORMATS` {srt, vtt, ass, txt}, `SUB_EXT` (readable inputs), `is_subtitle`, `write_subs`
  (format by extension; VTT escapes `& < >`, ASS escapes `{}` and `\`), `read_subs` → `_read_ass` /
  `_read_srt_vtt`, `_read_text` (UTF-8/UTF-16 BOM/cp1250).
- LLM: `ENGINES`, `ENGINE_FIELDS`, `ENGINE_KEY`, `DEFAULTS`, JSON `SCHEMA` (`{"translations":[{id,text}]}`
  used for both tasks), prompts `SYSTEM` (translate) and `SYSTEM_CORRECT` (proofread).
  `_llm(engine, keys, settings)` → `(ask, chunk)`; `_llm_cues(..., task="translate"|"correct")` batches
  with retries; `translate()`; `correct()` (rejects changes with difflib ratio < 0.5); per-engine
  `_ask_cli/_ask_api/_ask_codex/_ask_openai`, `_translate_deepl`. `check_engine`, `engine_info`, `list_models`.
- Config/keys: `CONFIG` path, `WHISPER_MODELS/SIZES/RECOMMENDED`, `MEDIA_EXT`, `load_config`/`save_config`
  (atomic), keyring `set_key`/`api_keys` (env fallbacks `KEY_ENV`). `__version__`.
- Job: `Options` dataclass (language, model, targets, engine, context, chars, lines, fmt, out_dir, keys,
  settings, on_exists, correct). `plan_outputs` (asks about existing files up front) →
  `process_file` (transcribe or read subs → optional `correct` → save source → parallel translations).
  Output names `name.<lang>.<fmt>`; `output_path`/`free_name` give `name.en (2).srt` copies.
  Progress weights `STT_WEIGHT`, `CORRECT_WEIGHT`, `TRANSLATE_WEIGHT`; progress never goes backwards.

## gui.py structure

- Palette tuples `(light, dark)` at top; `apply_theme`; `CheckGrid` (one canvas for 32 checkboxes — perf);
  `Tooltip`; `ExistsPrompt` (in-window overwrite/copy/skip panel); `Card`.
- `App.build()` — 3 columns: col 0 `_files_card`, `_stt_card`, `_format_card`; col 1 `_translate_card`;
  col 2 `_log_card` (takes extra width/height). Bottom: Generate/Stop button, Open folder, progress bar.
  `_fit_window` sizes the window to content; `poll()` re-fits when `body` reqheight changes.
  `on_ui_lang` destroys and rebuilds `self.body` (state must live on `App`, not widgets).
- STT card: model selector, "Proofread with an LLM" checkbox (`_update_correct_state`: off for DeepL or
  no model), download panel (`_update_model_state`, `download_model`, `_download_done`).
  `model_pref` = saved choice (kept even if another, downloaded model is shown).
- Threading: worker `work()` runs `core.plan_outputs`/`process_file`; talks to Tk only through
  `self.q` (`log`, `file`, `progress`, `info`, `ask_exists`, `models`, `output`, `dl_progress`,
  `dl_done`, `done`), handled in `_handle`. Without a cached model, media files are skipped.
- Log: entries are `i18n.Msg` (str subclass with `.key/.kw/.lang`); `LOG_STYLE` maps key → (style, icon),
  `LOG_SHORT_PATH` keys show basenames, `LOG_END` keys are job summaries. `_style_log` (tags, re-run on
  light/dark switch), `_log_write`, `log_entries` (replayed after rebuild).
- Settings autosave: `_autosave` → `_save_now` → `_collect` into `self.cfg` → `core.save_config`.
- Windows icons: `_win_icons` sets exact-DPI `WM_SETICON` frames.

## i18n

`t(key, in_lang=None, **kw)` returns `Msg`. Do not name a kwarg `in_lang`; many messages use `lang=`.
Add every new string to `S` with both languages. `set_lang(saved or None)` → saved choice, else
`system_lang()` (Windows UI language / macOS AppleLanguages / gettext env), English fallback.
`decimal()` formats numbers with the UI decimal separator.

## CLI

`generator-cli` options mirror GUI: `-l -t -e -m --download-model --llm-model --llm-url -c -o -f --correct
--chars --lines --overwrite --list-languages --ui-lang`. A missing Whisper model is downloaded only after
a y/N prompt (tty) or with `--download-model`; otherwise media files are skipped.

## Workflow

- Commit only when asked; work on a feature branch, then `git merge --ff-only` into `main` when the user
  asks to merge. Commit messages in English, end with the Co-Authored-By line.
- Release: bump `core.__version__`, commit, merge, push `main`, `tools/build_release.py`, smoke-test an
  extracted archive, then (after the user confirms) `gh release create vX.Y.Z --target main` with the
  6 archives and English notes in the same layout as v1.0.0/v1.1.0.
- After UI changes, verify with screenshots (light/dark, PL/EN) before reporting.
