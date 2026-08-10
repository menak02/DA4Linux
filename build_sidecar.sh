#!/bin/bash
set -e

echo "==> Detecting rustc target triple..."
TARGET_TRIPLE=$(rustc -vV | grep host | awk '{print $2}')
echo "Target triple: $TARGET_TRIPLE"

echo "==> Compiling DA4Linux with PyInstaller..."
cd "$(dirname "$0")"

# Use sidecar_entry.py (a top-level script with absolute imports) as the
# entrypoint so PyInstaller can find and bundle the entire da4linux package.
# --collect-all bundles the whole da4linux package (submodules + data files).
# --paths src/ puts the package on the path during analysis.
pyinstaller \
  --onefile \
  --name da4linux-cli \
  --collect-all da4linux \
  --paths src \
  --hidden-import da4linux \
  --hidden-import da4linux.cli \
  --hidden-import da4linux.generator \
  --hidden-import da4linux.detect \
  --hidden-import da4linux.parser \
  --hidden-import da4linux.plugin_db \
  --hidden-import da4linux.constants \
  --hidden-import da4linux.ir_generator \
  --hidden-import da4linux.profiles \
  sidecar_entry.py

echo "==> Moving binary to Tauri bin folder..."
mkdir -p ui/src-tauri/bin
cp dist/da4linux-cli "ui/src-tauri/bin/da4linux-cli-$TARGET_TRIPLE"
chmod +x "ui/src-tauri/bin/da4linux-cli-$TARGET_TRIPLE"

echo "==> Sidecar successfully built and moved to ui/src-tauri/bin/da4linux-cli-$TARGET_TRIPLE"
