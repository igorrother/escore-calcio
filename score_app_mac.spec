# PyInstaller spec for macOS (Apple Silicon, arm64).
#
# Build via GitHub Actions (.github/workflows/release.yml) on a macos-latest
# runner, OR manually on a Mac with:
#
#     python -m venv .venv
#     .venv/bin/pip install -r requirements.txt
#     .venv/bin/pyinstaller --noconfirm score_app_mac.spec
#
# Output:  dist/EscoreCalcio.app  (drag into /Applications or zip it).
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Same lazy-import collection as the Windows spec.
hiddenimports = (
    collect_submodules("pydicom")
    + collect_submodules("pydicom.encoders")
    + collect_submodules("pydicom.pixel_data_handlers")
    + collect_submodules("pydicom.pixels")
    + collect_submodules("skimage")
    + collect_submodules("pylibjpeg")
    + collect_submodules("libjpeg")
    + collect_submodules("openjpeg")
    + collect_submodules("rle")
)

datas = (
    collect_data_files("skimage")
    + collect_data_files("pylibjpeg")
    + collect_data_files("libjpeg")
    + collect_data_files("openjpeg")
    + collect_data_files("rle")
)

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy.spatial.cKDTree",
        "IPython",
        "jupyter",
        "notebook",
        "pandas",
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EscoreCalcio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,           # use the runner's native arch (arm64 on macos-latest)
    codesign_identity=None,     # unsigned for now — users get a one-time Gatekeeper warning
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EscoreCalcio",
)

app = BUNDLE(
    coll,
    name="EscoreCalcio.app",
    icon=None,
    bundle_identifier="com.igorrother.escorecalcio",
    version="1.0",
    info_plist={
        "CFBundleName": "Escore de Calcio",
        "CFBundleDisplayName": "Escore de Calcio de Agatston",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1.0",
        "CFBundleIdentifier": "com.igorrother.escorecalcio",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "NSRequiresAquaSystemAppearance": False,  # allow dark-mode rendering
        "LSMinimumSystemVersion": "11.0",          # Big Sur (first Apple-Silicon OS)
        "NSHumanReadableCopyright": "© 2026 Igor Rother Cesar de Oliveira. Research and educational use only.",
    },
)
