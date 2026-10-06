"""Entry point for the sidecar (and the PyInstaller build)."""

from __future__ import annotations

import argparse
import os
import sys
import threading

import uvicorn

from app.main import create_app


def exit_when_stdin_closes() -> None:
    """Quit once the parent app goes away.

    The desktop shell keeps our stdin open for as long as it lives, so EOF means it exited or crashed.
    This also covers the PyInstaller one-file launcher, whose child process outlives a killed parent.
    """

    def watch() -> None:
        try:
            while sys.stdin.buffer.read(1024):
                pass
        except (OSError, ValueError):
            pass
        os._exit(0)

    threading.Thread(target=watch, daemon=True, name="parent-watch").start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume ATS backend")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", default=None, help="X-App-Token value (or RESUME_ATS_TOKEN env)")
    parser.add_argument(
        "--exit-on-stdin-close",
        action="store_true",
        help="Exit when stdin closes (used by the desktop shell)",
    )
    args = parser.parse_args()
    if args.exit_on_stdin_close:
        exit_when_stdin_closes()
    # The Tauri shell passes the token via the environment so it stays out of process listings.
    token = args.token or os.environ.get("RESUME_ATS_TOKEN") or None

    # Bind to loopback only; the app is local-first and must not be reachable from the network.
    uvicorn.run(create_app(token=token), host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
