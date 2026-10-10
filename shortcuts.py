"""Creates launchers with the app icon (run by setup.bat / setup.sh after installing):

    Windows  "Subtitle Generator" shortcut in the app folder and in the Start menu
    macOS    "Subtitle Generator.app" in the app folder (drag it to the Dock or Applications)
    Linux    "Subtitle Generator" entry in the application menu
"""
import os
import re
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "Subtitle Generator"
ICONS = os.path.join(DIR, "assets")


def windows():
    links = [os.path.join(DIR, NAME + ".lnk"),
             os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", NAME + ".lnk")]
    # ścieżki idą przez zmienne środowiskowe, więc spacje i znaki specjalne nie psują polecenia
    script = ("$w = New-Object -ComObject WScript.Shell; "
              "foreach ($p in $env:SG_LINKS -split '\\|') { $s = $w.CreateShortcut($p); "
              "$s.TargetPath = $env:SG_TARGET; $s.Arguments = '\"' + $env:SG_GUI + '\"'; "
              "$s.WorkingDirectory = $env:SG_DIR; $s.IconLocation = $env:SG_ICON; "
              "$s.Description = 'Video / audio to SRT subtitles'; $s.Save() }")
    env = dict(os.environ, SG_LINKS="|".join(links), SG_TARGET=os.path.join(DIR, ".venv", "Scripts", "pythonw.exe"),
               SG_GUI=os.path.join(DIR, "gui.py"), SG_DIR=DIR, SG_ICON=os.path.join(ICONS, "icon.ico"))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env, check=True)
    return links


def macos():
    with open(os.path.join(DIR, "core.py"), encoding="utf-8") as f:
        version = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
    app = os.path.join(DIR, NAME + ".app")
    os.makedirs(os.path.join(app, "Contents", "MacOS"), exist_ok=True)
    os.makedirs(os.path.join(app, "Contents", "Resources"), exist_ok=True)
    with open(os.path.join(ICONS, "icon.icns"), "rb") as src, \
            open(os.path.join(app, "Contents", "Resources", "icon.icns"), "wb") as dst:
        dst.write(src.read())
    with open(os.path.join(app, "Contents", "Info.plist"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>{NAME}</string>
  <key>CFBundleDisplayName</key><string>{NAME}</string>
  <key>CFBundleIdentifier</key><string>com.maclask.subtitlegenerator</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
""")
    launcher = os.path.join(app, "Contents", "MacOS", "launcher")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write(f'#!/bin/sh\nexec "{DIR}/.venv/bin/python" "{DIR}/gui.py"\n')
    os.chmod(launcher, 0o755)
    os.utime(app)  # Finder odświeża ikonę
    return [app]


def linux():
    apps = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
    os.makedirs(apps, exist_ok=True)
    entry = os.path.join(apps, "subtitle-generator.desktop")
    with open(entry, "w", encoding="utf-8") as f:
        f.write(f"""[Desktop Entry]
Type=Application
Name={NAME}
Comment=Video / audio to SRT subtitles
Exec="{DIR}/generator.sh"
Path={DIR}
Icon={ICONS}/icon.png
Terminal=false
Categories=AudioVideo;Video;
""")
    os.chmod(entry, 0o755)
    return [entry]


if __name__ == "__main__":
    make = {"win32": windows, "darwin": macos}.get(sys.platform, linux)
    for path in make():
        print("Created:", path)
