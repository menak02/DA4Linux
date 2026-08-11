#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

# Files to update relative to repo root
TAURI_CONF_PATH = Path("ui/src-tauri/tauri.conf.json")
PACKAGE_JSON_PATH = Path("ui/package.json")
PYPROJECT_TOML_PATH = Path("pyproject.toml")

def main():
    if not TAURI_CONF_PATH.exists():
        print(f"Error: {TAURI_CONF_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    # 1. Read current version from tauri.conf.json
    try:
        with open(TAURI_CONF_PATH, "r") as f:
            tauri_conf = json.load(f)
    except Exception as e:
        print(f"Error reading tauri.conf.json: {e}", file=sys.stderr)
        sys.exit(1)

    old_version = tauri_conf.get("version", "0.2.0")
    
    # 2. Parse and increment patch version
    parts = old_version.split(".")
    if len(parts) != 3:
        print(f"Error: Invalid version format '{old_version}'", file=sys.stderr)
        sys.exit(1)
    
    try:
        patch = int(parts[2])
    except ValueError:
        print(f"Error: Patch version is not an integer in '{old_version}'", file=sys.stderr)
        sys.exit(1)

    new_version = f"{parts[0]}.{parts[1]}.{patch + 1}"
    print(f"Bumping version: {old_version} -> {new_version}")

    # 3. Write back to tauri.conf.json
    tauri_conf["version"] = new_version
    try:
        with open(TAURI_CONF_PATH, "w") as f:
            json.dump(tauri_conf, f, indent=2)
            f.write("\n")
    except Exception as e:
        print(f"Error writing tauri.conf.json: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. Write to ui/package.json
    if PACKAGE_JSON_PATH.exists():
        try:
            with open(PACKAGE_JSON_PATH, "r") as f:
                pkg_json = json.load(f)
            pkg_json["version"] = new_version
            with open(PACKAGE_JSON_PATH, "w") as f:
                json.dump(pkg_json, f, indent=2)
                f.write("\n")
        except Exception as e:
            print(f"Error updating ui/package.json: {e}", file=sys.stderr)
            sys.exit(1)

    # 5. Write to pyproject.toml
    if PYPROJECT_TOML_PATH.exists():
        try:
            content = PYPROJECT_TOML_PATH.read_text()
            new_content = re.sub(
                r'(version\s*=\s*")[^"]+(")',
                f'\\g<1>{new_version}\\g<2>',
                content,
                count=1
            )
            PYPROJECT_TOML_PATH.write_text(new_content)
        except Exception as e:
            print(f"Error updating pyproject.toml: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
