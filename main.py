"""Entry point: open the main window. The disclaimer lives under Help -> About."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from calcium_score.ui.main_window import MainWindow


def _icon_path() -> Path | None:
    """Locate icon.png in the source tree or inside a PyInstaller bundle."""
    # PyInstaller stashes datas under sys._MEIPASS at runtime.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    p = base / "icon.png"
    return p if p.is_file() else None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Agatston Calcium Score")
    icon = _icon_path()
    if icon is not None:
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
