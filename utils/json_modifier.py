#!/usr/bin/env python3
"""Modify JSON files: add (merge) or remove properties."""

import argparse
import json
import os
import sys
from datetime import datetime


def create_backup(file_path: str) -> str:
    """Create backup file with timestamp. Returns backup path."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = f"{file_path}.backup{timestamp}"

    counter = 1
    final_path = backup_path
    while os.path.exists(final_path):
        final_path = f"{backup_path}({counter})"
        counter += 1

    with open(file_path, "r", encoding="utf-8") as src:
        content = src.read()
    with open(final_path, "w", encoding="utf-8") as dst:
        dst.write(content)

    return final_path


def deep_merge(target: dict, source: dict) -> dict:
    """Recursively merge source into target. Arrays are concatenated."""
    result = target.copy()

    for key, value in source.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                result[key] = result[key] + value
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def deep_remove(target: dict, pattern: dict) -> dict:
    """Recursively remove from target based on pattern.

    - pattern key with None/null value: remove key entirely
    - pattern key with empty dict {}: remove key entirely
    - pattern key with dict value: recurse into target[key]
    """
    result = target.copy()

    for key, value in pattern.items():
        if key not in result:
            continue

        if value is None or value == {}:
            del result[key]
        elif isinstance(value, dict) and isinstance(result[key], dict):
            result[key] = deep_remove(result[key], value)
            if result[key] == {}:
                pass
        else:
            del result[key]

    return result


def load_json(path: str) -> dict:
    """Load JSON from file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    """Save JSON to file with 2-space indent."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Modify JSON files: add (merge) or remove properties",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge properties from add.json into target.json
  python json_modifier.py target.json --add add.json

  # Remove properties defined in remove.json from target.json
  python json_modifier.py target.json --remove remove.json

Remove patterns:
  {"env": null}           - removes "env" field entirely
  {"env": {}}             - removes "env" field entirely
  {"env": {"field": null}} - removes only "env.field", keeps other env fields
""",
    )
    parser.add_argument("target", help="Target JSON file to modify")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", metavar="SRC", help="JSON file with properties to merge")
    group.add_argument("--remove", metavar="SRC", help="JSON file with properties to remove")

    args = parser.parse_args()

    if not os.path.exists(args.add or args.remove):
        src_file = args.add or args.remove
        print(f"ERROR: Source file not found: {src_file}", file=sys.stderr)
        sys.exit(1)

    source = load_json(args.add or args.remove)

    if os.path.exists(args.target):
        target = load_json(args.target)
        backup_path = create_backup(args.target)
        print(f"Backup: {backup_path}")
    else:
        if args.remove:
            print(f"ERROR: Target file not found: {args.target}", file=sys.stderr)
            sys.exit(1)
        target = {}
        print(f"Creating new file: {args.target}")

    if args.add:
        result = deep_merge(target, source)
        action = "Merged"
    else:
        result = deep_remove(target, source)
        action = "Removed"

    save_json(args.target, result)
    print(f"{action}: {args.target}")


if __name__ == "__main__":
    main()
