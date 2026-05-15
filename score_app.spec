# PyInstaller spec for the Agatston calcium-score app.
# Build with:  .venv\Scripts\pyinstaller --noconfirm score_app.spec
# Output:      dist\EscoreCalcio\EscoreCalcio.exe  (plus DLLs/data alongside)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# pydicom and scikit-image lazily import transfer-syntax codecs and submodules
# that PyInstaller's static analysis misses; collect them explicitly.
hiddenimports = (
    collect_submodules("pydicom")
    + collect_submodules("pydicom.encoders")
    + collect_submodules("pydicom.pixel_data_handlers")
    + collect_submodules("skimage")
)

datas = collect_data_files("skimage")

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
        # Trim the bundle: we don't use these heavy optional deps.
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
    upx=False,           # leave off; UPX often triggers AV false-positives
    console=False,       # GUI app — no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",   # uncomment + drop an icon.ico in the repo to brand the exe
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
