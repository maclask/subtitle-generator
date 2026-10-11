# Subtitle Generator

**English** · [Polski](README.pl.md)

Subtitle Generator creates subtitles from video and audio recordings and translates them into other languages. It supports SRT, WebVTT and ASS, as well as plain-text transcripts.

## Features

- **Speech recognition** runs locally with Whisper ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)), GPU-accelerated on Windows and Linux (NVIDIA CUDA) and CPU-based on macOS.
- **Subtitle segmentation** at sentence and phrase boundaries, with balanced line lengths and minimum display durations.
- **Transcript proofreading** (optional) with a language model: corrects misrecognized words, proper names and punctuation without changing subtitle timing.
- **Translation** with Claude (CLI or API), Codex CLI, the OpenAI API, local models in Ollama, any OpenAI-compatible API (e.g. OpenRouter, LM Studio), or DeepL. Subtitle timing is preserved.
- **Graphical and command-line interfaces** on Windows, macOS and Linux, available in English and Polish.

## Requirements

| Component | Requirement |
|---|---|
| Python | 3.10–3.13 ([python.org](https://www.python.org/downloads/)) |
| Disk space | up to about 6 GB (CUDA libraries and the Whisper model) |
| GPU (optional) | NVIDIA GPU with a current driver; without one, transcription runs on the CPU, several times slower |
| Translation and proofreading | one of the translators listed under [Translator setup](#translator-setup); not required for transcription alone |

## Installation

Installation packages are available under [Releases](https://github.com/maclask/subtitle-generator/releases/latest):

| System | Graphical and command-line interface | Command line only |
|---|---|---|
| Windows | `subtitle-generator-<version>-windows.zip` | `subtitle-generator-cli-<version>-windows.zip` |
| macOS | `subtitle-generator-<version>-macos.zip` | `subtitle-generator-cli-<version>-macos.zip` |
| Linux | `subtitle-generator-<version>-linux.tar.gz` | `subtitle-generator-cli-<version>-linux.tar.gz` |

The command-line package does not require tkinter and is intended for systems without a desktop environment, such as servers.

### Windows

1. Install Python 3.13 from [python.org](https://www.python.org/downloads/), keeping the **py launcher** option selected.
2. Extract the package or clone the repository: `git clone https://github.com/maclask/subtitle-generator`.
3. Run **`setup.bat`**. The script creates a virtual environment in `.venv` and installs the dependencies.
4. Start the application with the **Subtitle Generator** shortcut (in the application folder and the Start menu) or with `generator.bat`. For the command line, use `generator-cli.bat`.

### macOS

1. Install Python 3.13 from [python.org](https://www.python.org/downloads/) (includes tkinter) or with Homebrew: `brew install python@3.13 python-tk@3.13`.
2. Extract the package or clone the repository.
3. In the application folder, run:
   ```sh
   sh setup.sh
   ```
4. Start **Subtitle Generator.app** (created in the application folder) or run `./generator.sh`.

> macOS may block the application on first launch. To open it, choose **Open** from the application's context menu and confirm.

### Linux

1. Install Python with the tkinter and venv modules:
   ```sh
   sudo apt install python3 python3-tk python3-venv   # Debian / Ubuntu
   sudo dnf install python3 python3-tkinter          # Fedora
   ```
2. Extract the package (`tar xzf subtitle-generator-*-linux.tar.gz`) or clone the repository.
3. In the application folder, run:
   ```sh
   sh setup.sh
   ```
4. Start **Subtitle Generator** from the application menu or run `./generator.sh`.

### Whisper models

The speech recognition model is downloaded from within the application, in the **Speech recognition** section:

| Model | Size | Characteristics |
|---|---|---|
| `large-v3-turbo` | 1.6 GB | fast, accuracy close to `large-v3` (recommended) |
| `large-v3` | 3.1 GB | highest accuracy |
| `medium` | 1.5 GB | lower accuracy |

Downloads can be cancelled. Until a model is downloaded, video and audio files are skipped, while translation of existing subtitle files remains available. The command-line version asks for confirmation before downloading a missing model (`large-v3` by default); in scripts, `--download-model` downloads it without asking. Without a model, video and audio files are skipped.

## Translator setup

| Translator | Setup |
|---|---|
| **Claude CLI** (default) | Install [Claude Code](https://claude.com/claude-code), run `claude` and sign in with `/login`. No API key is required. The application looks for `claude` on the PATH and in the Claude desktop application. |
| **Claude API** | An [Anthropic API key](https://console.anthropic.com/) or the `ANTHROPIC_API_KEY` variable. |
| **Codex CLI** | `npm install -g @openai/codex`, then `codex login` (ChatGPT account). Codex runs as an agent with read access to local files; for subtitles from untrusted sources, another translator is recommended. |
| **OpenAI API** | An [OpenAI API key](https://platform.openai.com/api-keys) or the `OPENAI_API_KEY` variable, and a model name. |
| **Ollama** | Install [Ollama](https://ollama.com) and pull a model, e.g. `ollama pull qwen3`. Installed models appear in the list. Works offline; performance depends on available GPU memory. |
| **Custom API** | Any OpenAI-compatible server: URL, model and an optional key (`CUSTOM_API_KEY`), e.g. `https://openrouter.ai/api/v1` or LM Studio at `http://localhost:1234/v1`. |
| **DeepL** | A [DeepL API key](https://www.deepl.com/pro-api) (the Free plan is supported) or the `DEEPL_API_KEY` variable. Supports DeepL languages only and does not perform transcript proofreading. |

API keys entered in the application are stored in the system credential store: Credential Manager (Windows), Keychain (macOS), or Secret Service — GNOME Keyring or KWallet (Linux). They are not written to any application file.

## Usage

### Graphical interface

The interface language follows the system language (English or Polish; English for all other languages). The **PL / EN** switch changes the language, and the choice is saved.

1. **Files** — add video or audio recordings, or existing `.srt`, `.vtt` or `.ass` subtitles (translation only, no transcription; set the subtitle language in **Spoken language**). Files can be dragged into the window; dragging a folder adds all supported files in it.
2. **Speech recognition** — select the spoken language (detected automatically by default) and the model. If the selected language clearly does not match the recording, the detected language is used and a warning is shown in the log.
   The **Proofread with an LLM** option enables transcript proofreading: after transcription, the translator selected in the **Translation** section corrects misrecognized words, proper names and punctuation, using the **Context** field. Subtitle timing is unchanged, and translations are based on the corrected text. Corrections that deviate substantially from the original are rejected; if proofreading fails, the speech recognition output is saved.
3. **Subtitle format** — file type, maximum characters per line and lines per subtitle.
4. **Translation** — select the translator and target languages. Languages not in the list can be entered in **Other languages** (LLM translators only). The **Context** field accepts the topic, proper names, a glossary or rules, e.g. *do not translate the brand name*.
5. Click **Generate subtitles**. Progress for each file is shown in the **Log** column; **Open folder** shows the saved files.

### Command line

```sh
generator-cli.bat video.mp4 -l en -t pl,de          # Windows
./generator-cli.sh video.mp4 -l en -t pl,de         # macOS / Linux
```

| Option | Description |
|---|---|
| `-l en` | spoken or subtitle language (code or name); detected automatically by default, required for subtitle files |
| `-t pl,de,catalan` | target languages; languages not in `--list-languages` are supported by all translators except DeepL |
| `-e cli\|api\|codex\|openai\|ollama\|custom\|deepl` | translator (default: the one last used in the graphical interface, otherwise `cli`) |
| `--llm-model`, `--llm-url` | model for `api`, `openai`, `ollama`, `custom`; server URL for `ollama`, `custom` |
| `-m large-v3-turbo` | Whisper model: `large-v3` (default), `large-v3-turbo`, `medium` |
| `--download-model` | download a missing Whisper model without asking (e.g. in scripts) |
| `--correct` | proofread the transcript with the translator given in `-e` (except DeepL) |
| `-c "…"` | context for proofreading and translation |
| `-f vtt` | file format: `srt` (default), `vtt`, `ass`, `txt` |
| `--chars 42 --lines 2` | maximum characters per line and lines per subtitle |
| `-o folder` | output folder (default: the source file's folder) |
| `--overwrite` | overwrite existing files (by default a copy is saved, e.g. `video.en (2).srt`) |
| `--ui-lang en` | message language: `en` or `pl` (defaults to the language chosen in the graphical interface, otherwise the system language) |

### Recommended editing workflow

1. Generate subtitles in the spoken language.
2. Import them into your editing software (e.g. in Premiere Pro: **File → Import**) and make corrections.
3. Export the corrected subtitles to an SRT file.
4. Add the corrected file to the generator, set its language and translate it — translations will be based on the approved text.

## Output files

Files are saved in the source file's folder as `name.<language code>.<extension>`, e.g. `video.en.srt`, `video.pl.srt`.

| Format | Extension | Use |
|---|---|---|
| SRT | `.srt` | universal format: editing software, video platforms, media players |
| WebVTT | `.vtt` | HTML5 players and web services |
| ASS | `.ass` | Aegisub, VLC, mpv; includes a style (white text with an outline) |
| TXT | `.txt` | text only, without timecodes |

**Encoding.** Files are saved as UTF-8 without a byte order mark. Line endings follow the operating system convention (CRLF on Windows, LF on macOS and Linux). The output encoding is not configurable; if a target device requires a single-byte encoding such as Windows-1250, convert the file with an external tool (e.g. Subtitle Edit). Input files can be encoded as UTF-8, UTF-16 (with a byte order mark) or Windows-1250.

## Troubleshooting

| Message or symptom | Solution |
|---|---|
| *GPU failed … falling back to CPU* | Update the NVIDIA driver. Transcription continues on the CPU. |
| *Claude CLI: Failed to authenticate* | Run `claude` in a terminal and sign in with `/login`. |
| Slow translation with Ollama | Choose a smaller model that fits in GPU memory (e.g. 7–14B parameters). |
| *No system keychain available* (Linux) | Install and unlock GNOME Keyring or KWallet, or set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CUSTOM_API_KEY` or `DEEPL_API_KEY`. |
| `setup` cannot find Python | Install Python 3.10–3.13; newer versions may not be supported by all dependencies. |

Application settings (excluding API keys) are saved in `config.json` in the application folder.

## License

[GPL-3.0](LICENSE)
