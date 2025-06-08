#!/usr/bin/env python3
"""Build React frontend and copy compiled assets into Python package.

Run automatically from packaging pipeline or manually via:
    python tools/build_frontend.py

Assumes Node/NPM are available.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "webui"
DIST_DIR = FRONTEND_DIR / "dist"
TARGET_DIR = ROOT / "src" / "StrateQueue" / "webui_static"


def build_frontend() -> None:
    if not FRONTEND_DIR.exists():
        print("[frontend-build] webui directory not found, skipping build")
        return

    print("[frontend-build] Installing npm dependencies …")
    subprocess.check_call(["npm", "install"], cwd=FRONTEND_DIR)

    print("[frontend-build] Running vite build …")
    subprocess.check_call(["npm", "run", "build"], cwd=FRONTEND_DIR)

    if not DIST_DIR.exists():
        print("[frontend-build] Build failed: dist directory not found", file=sys.stderr)
        sys.exit(1)

    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    shutil.copytree(DIST_DIR, TARGET_DIR)
    print(f"[frontend-build] Copied {DIST_DIR} → {TARGET_DIR}")


if __name__ == "__main__":
    build_frontend() 