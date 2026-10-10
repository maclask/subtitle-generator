"""Builds release archives into dist/ from the committed state (HEAD).

    python tools/build_release.py

Produces, per system, a full package (GUI + command line) and a command-line-only package:
    subtitle-generator-<ver>-{windows,macos}.zip, subtitle-generator-<ver>-linux.tar.gz
    subtitle-generator-cli-<ver>-{windows,macos}.zip, subtitle-generator-cli-<ver>-linux.tar.gz
"""
import io
import os
import re
import subprocess
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

COMMON = ["LICENSE", "README.md", "README.pl.md", "core.py", "i18n.py", "cli.py", "requirements-cli.txt"]
GUI = ["gui.py", "requirements.txt", "shortcuts.py", "assets/icon.png", "assets/icon.ico", "assets/icon.icns"]
SYSTEMS = {
    "windows": {"cli": ["setup.bat", "generator-cli.bat"], "gui": ["generator.bat"], "fmt": "zip"},
    "macos": {"cli": ["setup.sh", "generator-cli.sh"], "gui": ["generator.sh", "generator.command"], "fmt": "zip"},
    "linux": {"cli": ["setup.sh", "generator-cli.sh"], "gui": ["generator.sh"], "fmt": "tar.gz"},
}
EXECUTABLE = (".sh", ".command")


def committed(path):
    """File content from HEAD (LF endings); .bat gets CRLF, which cmd.exe needs."""
    data = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, check=True).stdout
    if path.endswith((".png", ".ico", ".icns")):
        return data  # pliki binarne bez zmian
    data = data.replace(b"\r\n", b"\n")
    return data.replace(b"\n", b"\r\n") if path.endswith(".bat") else data


def build(name, files, fmt):
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"{name}.{fmt}")
    if fmt == "zip":
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                info = zipfile.ZipInfo(f"{name}/{f}", date_time=(2026, 1, 1, 0, 0, 0))
                info.external_attr = (0o100755 if f.endswith(EXECUTABLE) else 0o100644) << 16  # bity uruchamiania (macOS)
                info.create_system = 3  # Unix — inaczej rozpakowanie ignoruje bity uprawnień
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, committed(f))
    else:
        with tarfile.open(out, "w:gz") as tar:
            for f in files:
                data = committed(f)
                info = tarfile.TarInfo(f"{name}/{f}")
                info.size, info.mode = len(data), 0o755 if f.endswith(EXECUTABLE) else 0o644
                tar.addfile(info, io.BytesIO(data))
    return out


def main():
    with open(os.path.join(ROOT, "core.py"), encoding="utf-8") as f:
        version = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
    for system, spec in SYSTEMS.items():
        cli_files = COMMON + spec["cli"]
        print(build(f"subtitle-generator-{version}-{system}", cli_files + GUI + spec["gui"], spec["fmt"]))
        print(build(f"subtitle-generator-cli-{version}-{system}", cli_files, spec["fmt"]))


if __name__ == "__main__":
    main()
