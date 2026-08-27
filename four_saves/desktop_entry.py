from __future__ import annotations

import sys


def main() -> None:
    try:
        from .desktop import main as desktop_main
    except ImportError as error:
        if error.name and error.name.startswith("PySide6"):
            print(
                "4Saves Desktop needs the optional desktop package.\n"
                "Install it with: python3 -m pip install '4saves[desktop]'",
                file=sys.stderr,
            )
            raise SystemExit(2) from error
        raise
    desktop_main()
