"""Startup disclaimer and About dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import __version__

DISCLAIMER_TEXT = (
    "This software is provided for research and educational purposes only.\n\n"
    "It is NOT a medical device, has NOT been cleared by any regulatory body, "
    "and MUST NOT be used for clinical diagnosis, treatment, screening, or "
    "patient management decisions.\n\n"
    "Results are user-driven (manual ROIs) and depend on protocol, "
    "reconstruction, and operator judgment. The authors accept no liability "
    "for any use of this tool or its output."
)


class DisclaimerDialog(QDialog):
    """Modal startup disclaimer the user must explicitly accept."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Research / educational use only")
        self.setModal(True)
        self.resize(560, 320)

        layout = QVBoxLayout(self)

        title = QLabel("Agatston Calcium Score — Research Tool")
        font = QFont()
        font.setBold(True)
        font.setPointSize(13)
        title.setFont(font)
        layout.addWidget(title)

        body = QLabel(DISCLAIMER_TEXT)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        buttons = QDialogButtonBox(self)
        accept = buttons.addButton("I understand", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel = buttons.addButton("Quit", QDialogButtonBox.ButtonRole.RejectRole)
        accept.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        layout.addWidget(buttons)


class AboutDialog(QDialog):
    """Help -> About dialog."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setModal(True)
        self.resize(500, 320)

        layout = QVBoxLayout(self)
        title = QLabel(f"Agatston Calcium Score v{__version__}")
        font = QFont()
        font.setBold(True)
        font.setPointSize(13)
        title.setFont(font)
        layout.addWidget(title)

        body = QLabel(DISCLAIMER_TEXT)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        # Close button uses the "rejected" signal in some Qt versions; wire both:
        for btn in buttons.buttons():
            btn.clicked.connect(self.accept)
        layout.addWidget(buttons)
