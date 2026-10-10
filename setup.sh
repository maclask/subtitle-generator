#!/usr/bin/env sh
# Subtitle Generator - macOS / Linux setup.
# Needs Python 3.10-3.13 (the GUI package also needs tkinter):
#   Debian/Ubuntu:    sudo apt install python3-tk python3-venv
#   Fedora:           sudo dnf install python3-tkinter
#   macOS (Homebrew): brew install python-tk   (python.org builds include tkinter)
cd "$(dirname "$0")" || exit 1
DIR="$(pwd)"

PY=""
for v in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$v" >/dev/null 2>&1 &&
       "$v" -c "import sys; sys.exit(not (3,10)<=sys.version_info[:2]<=(3,13))" 2>/dev/null; then
        PY="$v"; break
    fi
done
[ -n "$PY" ] || { echo "Python 3.10-3.13 not found."; exit 1; }
GUI=0; [ -f gui.py ] && GUI=1   # the command-line package has no gui.py
if [ $GUI = 1 ]; then
    "$PY" -c "import tkinter" 2>/dev/null || { echo "tkinter is missing for $PY - see the comment at the top of setup.sh."; exit 1; }
fi
echo "Using: $PY"

"$PY" -m venv --clear .venv || exit 1
.venv/bin/python -m pip install --upgrade pip || exit 1
if [ $GUI = 1 ]; then REQ=requirements.txt; else REQ=requirements-cli.txt; fi
.venv/bin/python -m pip install -r "$REQ" || exit 1
chmod +x ./*.sh ./*.command 2>/dev/null
if [ $GUI = 0 ]; then echo "Done. Command line: ./generator-cli.sh --help"; exit 0; fi

if [ "$(uname)" = "Linux" ]; then  # application menu entry
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/subtitle-generator.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Subtitle Generator
Comment=Video / audio to SRT subtitles
Exec="$DIR/generator.sh"
Path=$DIR
Terminal=false
Categories=AudioVideo;Video;
DESKTOP
    echo "Added \"Subtitle Generator\" to the application menu."
fi
echo "Done. GUI: ./generator.sh (macOS: or double-click generator.command)   Command line: ./generator-cli.sh --help"
