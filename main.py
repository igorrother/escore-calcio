"""Entry point: open the main window. The disclaimer lives under Help -> About."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from calcium_score.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Agatston Calcium Score")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
