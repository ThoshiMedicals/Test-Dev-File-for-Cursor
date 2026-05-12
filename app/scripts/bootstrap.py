from __future__ import annotations

import subprocess
import sys


def main() -> None:
    # Runs schema migrations then seeds base categories.
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])
    subprocess.check_call([sys.executable, "-m", "app.scripts.seed_categories"])


if __name__ == "__main__":
    main()

