"""Removes `await load_extensions()` from main.py and runs the bot, which makes
it so that dev bot loads 0 extensions. Users will not have the option to select
dev bot commands.
"""

import subprocess
import time
from pathlib import Path

# Path to main.py relative to this script
MAIN_PATH = Path(__file__).parent.parent / "main.py"
TARGET_LINE = "await load_extensions()"


def comment_out_line(path: Path, target: str) -> bool:
    lines = path.read_text().splitlines(keepends=True)

    for i, line in enumerate(lines):
        if target in line and not line.strip().startswith("#"):
            lines[i] = f"# {line}"
            path.write_text("".join(lines))
            return True
    return False


def uncomment_line(path: Path, target: str) -> None:
    lines = path.read_text().splitlines(keepends=True)

    for i, line in enumerate(lines):
        if target in line and "#" in line:
            # Remove only the first '#' symbol (to avoid stripping intentional inline comments)
            hash_index = line.find("#")
            if hash_index != -1:
                lines[i] = line[hash_index + 2 :]
                path.write_text("".join(lines))
                return


if __name__ == "__main__":
    print("🔧 Commenting out 'await load_extensions()'...")
    modified = comment_out_line(MAIN_PATH, TARGET_LINE)

    try:
        print("🚀 Running main.py (will terminate in 10s)...")
        process = subprocess.Popen(["uv", "run", "python", str(MAIN_PATH)])

        time.sleep(10)

        print("🛑 Terminating main.py...")
        process.terminate()  # Graceful
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            print("❌ Graceful termination failed. Killing...")
            process.kill()  # Force kill if stuck

    except Exception as e:
        print(f"❌ Failed to run main.py: {e}")

    finally:
        if modified:
            print("♻️ Restoring 'await load_extensions()'...")
            uncomment_line(MAIN_PATH, TARGET_LINE)
        print("✅ Done.")
