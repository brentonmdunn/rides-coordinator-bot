#!/usr/bin/env python3
"""Generate a bcrypt hash for BYPASS_PASSWORD env var."""

import getpass
import sys

import bcrypt


def main() -> None:
    """Prompt for a password and print its bcrypt hash."""
    password = getpass.getpass("Enter bypass password: ")
    if not password:
        print("Error: password cannot be empty", file=sys.stderr)
        sys.exit(1)

    confirm = getpass.getpass("Confirm bypass password: ")
    if password != confirm:
        print("Error: passwords do not match", file=sys.stderr)
        sys.exit(1)

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    print(f"\nSet this in your .env:\n\nBYPASS_PASSWORD={hashed}\n")


if __name__ == "__main__":
    main()
