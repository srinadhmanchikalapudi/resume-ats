"""Bundle the FastAPI backend with PyInstaller and place it where Tauri expects its sidecar.

Tauri's externalBin requires the executable name to end with the Rust target triple,
e.g. resume-ats-backend-x86_64-pc-windows-msvc.exe. Run this on each target OS
(PyInstaller cannot cross-compile); the release workflow does so per runner.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
OUT_DIR = ROOT / "src-tauri" / "binaries"
NAME = "resume-ats-backend"


def target_triple() -> str:
    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}.get(machine)
    if arch is None:
        raise SystemExit(f"Unsupported CPU architecture: {machine}")
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"


def main() -> None:
    triple = target_triple()
    suffix = ".exe" if sys.platform == "win32" else ""
    work = BACKEND / "build"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconfirm",
        "--clean",
        "--name", NAME,
        "--distpath", str(BACKEND / "dist"),
        "--workpath", str(work),
        "--specpath", str(work),
        # uvicorn and keyring load parts of themselves dynamically, so collect them explicitly.
        "--collect-submodules", "uvicorn",
        "--collect-submodules", "keyring",
        "--copy-metadata", "keyring",
        str(BACKEND / "run.py"),
    ]
    subprocess.run(cmd, check=True, cwd=BACKEND)

    built = BACKEND / "dist" / f"{NAME}{suffix}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / f"{NAME}-{triple}{suffix}"
    shutil.copy2(built, target)
    print(f"Sidecar ready: {target}")


if __name__ == "__main__":
    main()
