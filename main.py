"""Entry point: show the research-use-only disclaimer, then the main window."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from calcium_score.ui.disclaimer import DisclaimerDialog
from calcium_score.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Agatston Calcium Score")

    if DisclaimerDialog().exec() != DisclaimerDialog.DialogCode.Accepted:
        return 0

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
