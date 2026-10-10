# Subtitle Generator

**English** · [Polski](README.pl.md)

Turn video or audio into ready-to-use `.srt` subtitles and translate them into other languages.
The files work in Premiere Pro, DaVinci Resolve, Final Cut Pro, YouTube and other tools that accept SRT.

- **Speech recognition:** Whisper large-v3 ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)), running locally. Uses an NVIDIA GPU (CUDA) on Windows and Linux, and the CPU on macOS.
- **Subtitle formatting:** subtitles are split at sentence and clause boundaries, with balanced lines and minimum display times.
- **Translation:** choose Claude (CLI or API), Codex CLI, OpenAI, a local model through Ollama, any OpenAI-compatible API (OpenRouter, LM Studio, Mistral…), or DeepL. The timing of every subtitle is kept.
- **GUI and command line** on Windows, macOS and Linux. The interface is available in English and Polish.

## Requirements

| Requirement | Details |
|---|---|
| Python | 3.10 – 3.13 ([python.org](https://www.python.org/downloads/)) |
| Disk | about 6 GB (CUDA libraries and the Whisper model) |
| GPU (optional) | NVIDIA with a recent driver. Without one, the CPU is used, which is several times slower. |
| Translation | one of the translators below. Transcription alone needs none. |

## Installation

Download the package for your system from [Releases](https://github.com/maclask/subtitle-generator/releases/latest):

| | GUI + command line | Command line only |
|---|---|---|
| Windows | `subtitle-generator-<version>-windows.zip` | `subtitle-generator-cli-<version>-windows.zip` |
| macOS | `subtitle-generator-<version>-macos.zip` | `subtitle-generator-cli-<version>-macos.zip` |
| Linux | `subtitle-generator-<version>-linux.tar.gz` | `subtitle-generator-cli-<version>-linux.tar.gz` |

The command-line package doesn't need tkinter, which makes it a good fit for servers.

### Windows

1. Install Python 3.13 from [python.org](https://www.python.org/downloads/). Keep the **py launcher** option enabled in the installer.
2. Unpack the Windows package, or run `git clone https://github.com/maclask/subtitle-generator`.
3. Double-click **`setup.bat`**. It creates a local environment in `.venv` and installs dependencies. This takes a few minutes.
4. Start the app with **`generator.bat`**, or use `generator-cli.bat` for the command line.

### macOS

1. Install Python 3.13 from [python.org](https://www.python.org/downloads/), which includes tkinter. With Homebrew, run `brew install python@3.13 python-tk@3.13` instead.
2. Unpack the macOS package, or clone the repository.
3. In Terminal, in the project folder, run:
   ```sh
   sh setup.sh
   ```
4. Start the app by double-clicking **`generator.command`**, or with `./generator.sh`.

> The first time, macOS may block `generator.command`. Right-click it, choose **Open**, then confirm.

### Linux

1. Install Python with tkinter and venv:
   ```sh
   sudo apt install python3 python3-tk python3-venv   # Debian / Ubuntu
   sudo dnf install python3 python3-tkinter          # Fedora
   ```
2. Unpack the Linux package (`tar xzf subtitle-generator-*-linux.tar.gz`), or clone the repository.
3. In the project folder, run:
   ```sh
   sh setup.sh
   ```
4. Start **Subtitle Generator** from the application menu (setup adds the entry), or run `./generator.sh`.

The Whisper model (about 3 GB for large-v3) downloads on the first transcription.

## Translator setup

| Translator | Setup |
|---|---|
| **Claude CLI** (default) | Install [Claude Code](https://claude.com/claude-code), run `claude` once and sign in with `/login`. No API key is needed. The app finds `claude` on your PATH or inside the Claude desktop app. |
| **Claude API** | Paste an [Anthropic API key](https://console.anthropic.com/), or set `ANTHROPIC_API_KEY`. |
| **Codex CLI** | `npm install -g @openai/codex`, then `codex login`. Uses your ChatGPT account. |
| **OpenAI API** | Paste an [OpenAI API key](https://platform.openai.com/api-keys) (or set `OPENAI_API_KEY`) and enter a model name. |
| **Ollama (local)** | Install [Ollama](https://ollama.com) and pull a model, e.g. `ollama pull qwen3`. Installed models appear in the list. Runs offline, but large models are slow on GPUs with little VRAM. |
| **Custom API** | Any OpenAI-compatible endpoint: server URL, model, and an optional key (`CUSTOM_API_KEY`). Examples: `https://openrouter.ai/api/v1`, LM Studio `http://localhost:1234/v1`. |
| **DeepL** | Paste a [DeepL API key](https://www.deepl.com/pro-api) (the Free plan works), or set `DEEPL_API_KEY`. Supports only DeepL's languages; use an LLM translator for the rest. |

Keys you enter in the app are stored in the system keychain: Credential Manager on Windows, Keychain on macOS, and Secret Service (GNOME Keyring or KWallet) on Linux. They are never written to the project folder.

## Usage

### GUI

1. **Add files**: video, audio, or an existing `.srt` file to translate it without transcription.
2. Choose the **spoken language** (or auto-detect) and the **model**. `large-v3` is the most accurate; `large-v3-turbo` is several times faster.
3. Optionally pick **target languages** and a translator. Use **Other languages** for anything not in the list (Claude only).
4. Optionally add **context**: topic, proper names, a glossary, or a rule such as *keep the brand name untranslated*.
5. Click **Generate subtitles**. Files are saved next to the source as `name.pl.srt`, `name.en.srt`, and so on.

### Command line

```sh
generator-cli.bat video.mp4 -l en -t pl,de          # Windows
./generator-cli.sh video.mp4 -l en -t pl,de         # macOS / Linux
```

| Option | Description |
|---|---|
| `-l en` | spoken / subtitle language (code or name); detected if omitted |
| `-t pl,de,catalan` | target languages; names outside `--list-languages` work with Claude only |
| `-e cli\|api\|codex\|openai\|ollama\|custom\|deepl` | translator (default: the one last used in the GUI, otherwise `cli`) |
| `--llm-model`, `--llm-url` | model / server URL for `openai`, `ollama`, `custom` |
| `-m large-v3-turbo` | Whisper model: `large-v3`, `large-v3-turbo`, `medium` |
| `-c "…"` | context for the translator |
| `-o folder` | output folder (default: next to the source file) |
| `--chars 42 --lines 2` | subtitle layout |
| `--ui-lang en` | message language (`en` or `pl`) |

### Recommended workflow for editing

1. Generate subtitles in the spoken language.
2. Import the `.srt` into your editor and correct it there.
3. Export the corrected subtitles as SRT.
4. Add the corrected `.srt` to the app and translate it. Translations then start from the corrected text.

In Premiere Pro: **File → Import**, select the `.srt` and drag it onto the timeline.

## Troubleshooting

| Problem | Fix |
|---|---|
| *GPU failed … falling back to CPU* | Update the NVIDIA driver. Transcription still works on the CPU, just more slowly. |
| *Claude CLI: Failed to authenticate* | Run `claude` in a terminal and sign in with `/login`. |
| Ollama translation is very slow | Choose a smaller model that fits in your GPU memory (e.g. 7–14B parameters). |
| *No system keychain available* (Linux) | Install and unlock GNOME Keyring or KWallet, or set `ANTHROPIC_API_KEY` / `DEEPL_API_KEY`. |
| `setup` cannot find Python | Install Python 3.10–3.13. Newer versions may not have every dependency yet. |

Settings (without keys) are saved in `config.json` in the project folder.

## License

[GPL-3.0](LICENSE)
