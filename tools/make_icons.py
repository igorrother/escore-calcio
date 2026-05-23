"""Generate platform icon files from icon.png.

Reads ``icon.png`` at the repo root and writes:

* ``icon.ico`` — multi-size Windows icon (16/32/48/64/128/256).
  Used by PyInstaller's EXE() ``icon=`` parameter so the .exe shows
  the app icon in File Explorer, the taskbar, and Alt-Tab.
* ``icon.icns`` — multi-size macOS icon (incl. Retina @2x variants).
  Used by PyInstaller's BUNDLE() ``icon=`` parameter so the .app
  shows the app icon in Finder and the Dock.

Run after editing ``icon.png`` so the embedded platform icons stay in
sync with the source. CI runs this automatically before PyInstaller.

Usage:
    python tools/make_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "icon.png"
ICO = REPO_ROOT / "icon.ico"
ICNS = REPO_ROOT / "icon.icns"

# Windows .ico needs 16/32/48 for taskbar + Alt-Tab; 64/128/256 for
# Start menu, file properties pane, and high-DPI displays.
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if not SRC.exists():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1

    src = Image.open(SRC).convert("RGBA")
    if src.size != (1024, 1024):
        print(
            f"warning: icon.png is {src.size}, expected 1024x1024",
            file=sys.stderr,
        )

    src.save(ICO, format="ICO", sizes=ICO_SIZES)
    print(f"wrote {ICO.relative_to(REPO_ROOT)} ({ICO.stat().st_size} bytes)")

    # Pillow's ICNS writer picks a sensible set of sub-images from the
    # source. Larger source resolution → more variants embedded.
    src.save(ICNS, format="ICNS")
    print(f"wrote {ICNS.relative_to(REPO_ROOT)} ({ICNS.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
