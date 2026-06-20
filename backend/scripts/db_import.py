#!/usr/bin/env python3
"""
Import (restore) a database backup produced by db_export.py.

Auto-detects whether the input is a plain SQLite file or a Fernet-encrypted
blob, validates it with PRAGMA integrity_check, backs up the current database
first, then atomically swaps the restored file into place.

IMPORTANT: stop the app/container before importing — there must be no open
writers on the target database file.

Usage:
    uv run python scripts/db_import.py --input PATH [--force]
"""

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from db_backup_common import (
    BACKEND_DIR,
    ENCRYPTION_KEY_ENV,
    InvalidToken,
    decrypt_bytes,
    get_encryption_key,
    integrity_ok,
    is_sqlite_bytes,
    resolve_db_path,
    warn_no_encryption,
)


def _decode_input(raw: bytes) -> bytes:
    """Return raw SQLite bytes, decrypting first if the input is encrypted."""
    if is_sqlite_bytes(raw):
        warn_no_encryption("imported")
        return raw

    key = get_encryption_key()
    if key is None:
        print(
            f"Error: input is not a plain SQLite file and {ENCRYPTION_KEY_ENV} is not set.\n"
            "Set the same key used to create the backup, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        decrypted = decrypt_bytes(raw, key)
    except InvalidToken:
        print(
            f"Error: could not decrypt the backup. The {ENCRYPTION_KEY_ENV} is wrong or the file is corrupt.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not is_sqlite_bytes(decrypted):
        print("Error: decrypted data is not a valid SQLite file.", file=sys.stderr)
        sys.exit(1)
    return decrypted


def main() -> None:
    """Parse args, validate the backup, and restore it."""
    parser = argparse.ArgumentParser(
        description="Restore a database backup created by db_export.py."
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Path to the backup file (.db or .db.enc)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the existing non-empty database.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    db_path = resolve_db_path()
    if db_path.exists() and db_path.stat().st_size > 0 and not args.force:
        print(
            f"Error: a non-empty database already exists at {db_path}.\n"
            "Stop the app/container, then re-run with --force to overwrite it.",
            file=sys.stderr,
        )
        sys.exit(1)

    sqlite_bytes = _decode_input(args.input.read_bytes())

    # Validate by writing to a temp file inside the repo dir and integrity-checking it.
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    staged = BACKEND_DIR / f".db-import-{timestamp}.tmp"
    staged.write_bytes(sqlite_bytes)
    try:
        if not integrity_ok(staged):
            print("Error: backup failed integrity check; nothing was changed.", file=sys.stderr)
            sys.exit(1)

        print("Make sure the app/container is STOPPED — there must be no open writers on the database.")

        # Back up the current DB first so a bad import is recoverable.
        if db_path.exists():
            backup_path = db_path.with_name(f"{db_path.name}.bak-{timestamp}")
            shutil.copy2(db_path, backup_path)
            print(f"Backed up current database to {backup_path}")

        db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged), str(db_path))
    finally:
        staged.unlink(missing_ok=True)

    print(f"\nRestored {args.input} -> {db_path}")
    print(
        "On next startup, entrypoint.sh runs `alembic upgrade head`, migrating an older backup forward."
    )


if __name__ == "__main__":
    main()
