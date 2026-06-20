#!/usr/bin/env python3
"""
Export the entire SQLite database to a single portable backup file.

Takes a consistent snapshot via SQLite's online backup API (safe even while the
app is running and holds the file open), then writes it out — encrypted with
Fernet if BACKUP_ENCRYPTION_KEY is set, otherwise as a plain .db file with a
loud warning.

Usage:
    uv run python scripts/db_export.py [--output PATH]
    uv run python scripts/db_export.py --gen-key
"""

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from db_backup_common import (
    BACKEND_DIR,
    encrypt_bytes,
    generate_key,
    get_encryption_key,
    integrity_ok,
    resolve_db_path,
    warn_no_encryption,
)


def _snapshot(db_path: Path, snapshot_path: Path) -> None:
    """Copy ``db_path`` into ``snapshot_path`` via the SQLite backup API."""
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(snapshot_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def main() -> None:
    """Parse args and export (or generate a key)."""
    parser = argparse.ArgumentParser(description="Export the SQLite database to a backup file.")
    parser.add_argument(
        "--output", type=Path, help="Output path (default: timestamped file in backend dir)."
    )
    parser.add_argument(
        "--gen-key",
        action="store_true",
        help="Print a fresh Fernet encryption key and exit.",
    )
    args = parser.parse_args()

    if args.gen_key:
        print(generate_key())
        return

    db_path = resolve_db_path()
    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    key = get_encryption_key()
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    suffix = ".db.enc" if key else ".db"
    output = args.output or (BACKEND_DIR / f"bot-db-backup-{timestamp}{suffix}")

    # Temp snapshot lives inside the repo dir (never /tmp) so an OS temp-dir
    # sweep can't corrupt an in-progress export.
    snapshot_path = BACKEND_DIR / f".db-export-{timestamp}.tmp"
    try:
        _snapshot(db_path, snapshot_path)
        if not integrity_ok(snapshot_path):
            print("Error: snapshot failed integrity check; aborting.", file=sys.stderr)
            sys.exit(1)

        data = snapshot_path.read_bytes()
        if key:
            output.write_bytes(encrypt_bytes(data, key))
        else:
            warn_no_encryption("exported")
            output.write_bytes(data)
    finally:
        snapshot_path.unlink(missing_ok=True)

    size_kb = output.stat().st_size / 1024
    print(f"\nExported {db_path.name} -> {output} ({size_kb:.1f} KB)")
    if key:
        print("This backup is ENCRYPTED. You must set the same BACKUP_ENCRYPTION_KEY to import it.")


if __name__ == "__main__":
    main()
