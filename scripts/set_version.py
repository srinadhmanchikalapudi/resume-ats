"""Stamp one version into every place that carries it. Usage: set_version.py 1.2.3 (or v1.2.3)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Could not find a version to update in {path}")
    path.write_text(new_text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: set_version.py <version>")
    version = sys.argv[1].removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", version):
        raise SystemExit(f"Not a valid semantic version: {version}")

    conf = ROOT / "src-tauri" / "tauri.conf.json"
    data = json.loads(conf.read_text(encoding="utf-8"))
    data["version"] = version
    conf.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    replace_once(ROOT / "src-tauri" / "Cargo.toml", r'^version = ".*"$', f'version = "{version}"')
    replace_once(ROOT / "backend" / "app" / "__init__.py", r'__version__ = ".*"', f'__version__ = "{version}"')
    print(f"Version set to {version}")


if __name__ == "__main__":
    main()
