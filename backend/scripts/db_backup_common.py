"""
Shared helpers for the database export/import CLI scripts.

These scripts operate on the raw SQLite file (not the ORM) so a backup is a
byte-exact clone — every table, index, and the ``alembic_version`` row included.

Run via:
    uv run python scripts/db_export.py
    uv run python scripts/db_import.py --input <file>
"""

import os
import sqlite3
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# Default matches bot/core/database.py and the parsing in entrypoint.sh.
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./db/bot.db"
SQLITE_MAGIC = b"SQLite format 3\x00"  # First 16 bytes of any SQLite 3 file.
ENCRYPTION_KEY_ENV = "BACKUP_ENCRYPTION_KEY"

# Resolve paths relative to the backend dir (parent of scripts/) so the scripts
# behave the same regardless of the current working directory.
BACKEND_DIR = Path(__file__).resolve().parent.parent


def resolve_db_path() -> Path:
    """
    Resolve the live SQLite file path from ``DATABASE_URL``.

    Mirrors the prefix stripping done in entrypoint.sh so both agree on which
    file is the database.
    """
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    path_str = url.removeprefix("sqlite+aiosqlite:///").removeprefix("sqlite:///")
    path = Path(path_str)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    return path


def get_encryption_key() -> bytes | None:
    """Return the Fernet key from the env var, or ``None`` if unset/empty."""
    key = os.getenv(ENCRYPTION_KEY_ENV, "").strip()
    return key.encode() if key else None


def generate_key() -> str:
    """Return a fresh, urlsafe-base64 Fernet key."""
    return Fernet.generate_key().decode()


def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Encrypt ``data`` with the given Fernet ``key``."""
    return Fernet(key).encrypt(data)


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    """
    Decrypt ``blob`` with the given Fernet ``key``.

    Raises ``InvalidToken`` if the key is wrong or the data is corrupt.
    """
    return Fernet(key).decrypt(blob)


def is_sqlite_bytes(data: bytes) -> bool:
    """Return True if ``data`` begins with the SQLite 3 file magic."""
    return data[:16] == SQLITE_MAGIC


def integrity_ok(db_path: Path) -> bool:
    """Run ``PRAGMA integrity_check`` and return True if the DB reports ``ok``."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row) and row[0] == "ok"
    finally:
        conn.close()


def warn_no_encryption(context: str) -> None:
    """
    Print a prominent warning to stderr when no encryption key is set.

    ``context`` is a short phrase like "exported" or "imported".
    """
    bar = "!" * 72
    print(
        f"\n{bar}\n"
        f"!!  WARNING: {ENCRYPTION_KEY_ENV} is not set.\n"
        f"!!  The database is being {context} UNENCRYPTED.\n"
        f"!!  It contains user emails, names, and Discord identities.\n"
        f"!!  Only move this file over a trusted channel (e.g. scp over SSH)\n"
        f"!!  and delete it once the migration is complete.\n"
        f"!!  To encrypt, generate a key with `--gen-key` and set {ENCRYPTION_KEY_ENV}.\n"
        f"{bar}\n",
        file=sys.stderr,
    )


# Re-exported so callers can catch decryption failures without importing cryptography.
__all__ = [
    "ENCRYPTION_KEY_ENV",
    "InvalidToken",
    "decrypt_bytes",
    "encrypt_bytes",
    "generate_key",
    "get_encryption_key",
    "integrity_ok",
    "is_sqlite_bytes",
    "resolve_db_path",
    "warn_no_encryption",
]
