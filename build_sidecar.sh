#!/bin/bash
set -e

echo "==> Detecting rustc target triple..."
TARGET_TRIPLE=$(rustc -vV | grep host | awk '{print $2}')
echo "Target triple: $TARGET_TRIPLE"

echo "==> Compiling DA4Linux with PyInstaller..."
# Navigate to project root just in case
cd "$(dirname "$0")"

# We run pyinstaller on cli.py
pyinstaller --onefile --name da4linux src/da4linux/cli.py

echo "==> Moving binary to Tauri bin folder..."
mkdir -p ui/src-tauri/bin
cp dist/da4linux "ui/src-tauri/bin/da4linux-$TARGET_TRIPLE"
chmod +x "ui/src-tauri/bin/da4linux-$TARGET_TRIPLE"

echo "==> Sidecar successfully built and moved to ui/src-tauri/bin/da4linux-$TARGET_TRIPLE"
