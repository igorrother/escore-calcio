"""About dialog and the research-use-only disclaimer text."""

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

from .. import __author__, __version__

DISCLAIMER_TEXT = (
    "Este software é fornecido apenas para fins de pesquisa e ensino.\n\n"
    "NÃO é um dispositivo médico, NÃO foi aprovado por nenhum órgão regulador "
    "e NÃO deve ser utilizado para diagnóstico, tratamento, rastreamento ou "
    "decisões de manejo de pacientes.\n\n"
    "Os resultados dependem das ROIs manuais do usuário, do protocolo, da "
    "reconstrução e do julgamento do operador. Os autores não se "
    "responsabilizam por qualquer uso desta ferramenta ou de seus resultados."
)


class AboutDialog(QDialog):
    """Help -> About dialog. Holds the research-use-only disclaimer text."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Sobre")
        self.setModal(True)
        self.resize(500, 320)

        layout = QVBoxLayout(self)
        title = QLabel(f"Escore de Cálcio de Agatston v{__version__}")
        font = QFont()
        font.setBold(True)
        font.setPointSize(13)
        title.setFont(font)
        layout.addWidget(title)

        author = QLabel(f"Desenvolvido por {__author__}")
        author_font = QFont()
        author_font.setItalic(True)
        author.setFont(author_font)
        layout.addWidget(author)

        body = QLabel(DISCLAIMER_TEXT)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Fechar")
        for btn in buttons.buttons():
            btn.clicked.connect(self.accept)
        layout.addWidget(buttons)
