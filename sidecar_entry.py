#!/usr/bin/env python3
"""
Sidecar entry point for PyInstaller.
This file is used ONLY by PyInstaller — it is NOT the package CLI.
Using a top-level script with absolute imports avoids PyInstaller's
'attempted relative import with no known parent package' crash.
"""
import sys
import os

# Ensure the bundled package is on the path (PyInstaller sys._MEIPASS)
if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    if base not in sys.path:
        sys.path.insert(0, base)

from da4linux.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
