# PyInstaller spec — gera um único executável da GUI.
# Uso:  pyinstaller --clean packaging/sfasst-gui.spec
from pathlib import Path

block_cipher = None

REPO = Path.cwd()
SRC = str(REPO / "src")
DATA_DIR = REPO / "src" / "sfasst" / "data"

# (origem_no_disco, destino_dentro_do_bundle)
datas = []
for tsv in sorted(DATA_DIR.glob("*.tsv")):
    datas.append((str(tsv), "sfasst/data"))
for ext in sorted((DATA_DIR / "external").glob("*")):
    datas.append((str(ext), "sfasst/data/external"))

a = Analysis(
    [str(REPO / "src" / "sfasst" / "gui" / "__main__.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "sfasst.gui.tabs.quests",
        "sfasst.gui.tabs.skills",
        "sfasst.gui.tabs.research",
        "sfasst.gui.tabs.status",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sfasst-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
