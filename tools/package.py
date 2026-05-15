"""Package the built dist\\EscoreCalcio folder as a versioned end-user ZIP.

Expects dist\\EscoreCalcio\\EscoreCalcio.exe to already exist (run
build_windows.bat first or let package_zip.bat chain it). Writes:

    dist\\LEIA-ME.txt                   (a copy of the end-user readme)
    dist\\EscoreCalcio\\LEIA-ME.txt     (inside the zipped folder)
    dist\\EscoreCalcio-vX.Y.zip         (the distributable)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from calcium_score import __author__, __version__  # noqa: E402


DIST = ROOT / "dist"
APP_DIR = DIST / "EscoreCalcio"
EXE = APP_DIR / "EscoreCalcio.exe"

README_PT = f"""\
Escore de Cálcio de Agatston v{__version__}
Desenvolvido por {__author__}

============================================================
COMO USAR
============================================================

1. Extraia esta pasta para qualquer local (Área de Trabalho,
   Documentos, etc.).
2. Dê duplo clique em "EscoreCalcio.exe" para abrir o aplicativo.
3. Em "Arquivo" -> "Abrir Pasta..." (ou "Abrir ZIP...") escolha
   um estudo DICOM, ou arraste uma pasta/ZIP diretamente para a janela.

NÃO mova "EscoreCalcio.exe" para fora desta pasta. Ele precisa da
subpasta "_internal" ao lado para funcionar.

============================================================
AVISO DO WINDOWS NA PRIMEIRA EXECUÇÃO
============================================================

Na primeira vez que abrir, o Windows pode exibir a mensagem
"O Windows protegeu seu PC" ("Windows protected your PC"). Isso
acontece porque o aplicativo ainda não está assinado digitalmente.

Para abrir mesmo assim:
  - clique em "Mais informações"
  - depois clique em "Executar assim mesmo"

============================================================
AVISO IMPORTANTE
============================================================

Este software é fornecido APENAS para fins de pesquisa e ensino.
NÃO é um dispositivo médico, NÃO foi aprovado por nenhum órgão
regulador, e NÃO deve ser utilizado para diagnóstico, tratamento,
rastreamento ou decisões de manejo de pacientes.

Os resultados dependem das ROIs manuais do usuário, do protocolo,
da reconstrução e do julgamento do operador.
"""


def main() -> int:
    if not EXE.is_file():
        print(f"[ERROR] {EXE} not found.")
        print("Run build_windows.bat first (which produces dist\\EscoreCalcio\\).")
        return 1

    # Write end-user README inside the app folder so it ends up in the zip.
    readme_inside = APP_DIR / "LEIA-ME.txt"
    readme_inside.write_text(README_PT, encoding="utf-8")
    print(f"Wrote {readme_inside}")

    # Also drop a sibling copy in dist/ so the recipient can read it without
    # extracting (and so people who share just the zip have the same text).
    (DIST / "LEIA-ME.txt").write_text(README_PT, encoding="utf-8")

    # Zip the folder. base_dir="EscoreCalcio" gives a clean top-level folder
    # inside the archive, so extraction creates one "EscoreCalcio" directory.
    out_stem = DIST / f"EscoreCalcio-v{__version__}"
    if out_stem.with_suffix(".zip").exists():
        out_stem.with_suffix(".zip").unlink()

    archive_path = Path(
        shutil.make_archive(
            base_name=str(out_stem),
            format="zip",
            root_dir=str(DIST),
            base_dir="EscoreCalcio",
        )
    )
    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {archive_path}  ({size_mb:.0f} MB)")
    print()
    print("Distribute the .zip via Google Drive / OneDrive / Dropbox / email.")
    print("Recipients just extract the folder anywhere and double-click")
    print("EscoreCalcio.exe — no installation required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
