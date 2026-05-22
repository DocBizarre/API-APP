# ─────────────────────────────────────────────────────────────────────────────
# ems_launcher.spec — Fichier PyInstaller pour générer EMS_Launcher.exe
#
# Usage :
#   pip install pyinstaller pillow
#   pyinstaller ems_launcher.spec
#
# Le .exe se trouvera dans  dist/EMS_Launcher/EMS_Launcher.exe
# Copier tout le dossier dist/EMS_Launcher sur la machine cible.
# ─────────────────────────────────────────────────────────────────────────────

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).resolve()

# ── Fichiers et dossiers à embarquer ─────────────────────────────────────────
# Pour chaque (source, dossier_destination) : copié tel quel à côté du .exe
datas = []

# Dossiers complets des 5 apps (.py + assets + HTML)
for sub in ("ems_project", "garanties_app", "amelioration_app", "BI_app"):
    src = ROOT / sub
    if src.is_dir():
        datas.append((str(src), sub))

# logo_data.py à la racine (utilisé par le launcher)
if (ROOT / "logo_data.py").is_file():
    datas.append((str(ROOT / "logo_data.py"), "."))

# ── Modules à inclure explicitement (cachés des analyses automatiques) ──────
hiddenimports = [
    # Tkinter / PIL
    "tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.simpledialog",
    "tkinter.filedialog", "tkinter.colorchooser",
    "PIL", "PIL.Image", "PIL.ImageTk", "PIL.ImageDraw",
    # Stdlib
    "sqlite3", "csv", "json", "webbrowser", "http.server", "socket",
    "subprocess", "multiprocessing", "multiprocessing.spawn",
    "base64", "io", "datetime", "pathlib",
    # Modules des apps (résolus dynamiquement par le worker)
    "main", "database", "bon_generator", "logo_data",
    "amelioration_generator", "garantie_generator", "csv_importer", "mailer",
    "app_garanties", "app_amelioration", "app_bi",
]


block_cipher = None

a = Analysis(
    ['ems_launcher.py'],
    pathex=[str(ROOT),
            str(ROOT / "ems_project"),
            str(ROOT / "garanties_app"),
            str(ROOT / "amelioration_app"),
            str(ROOT / "BI_app")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='EMS_Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,        # False = pas de console noire (passer à True pour debug)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='favicon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EMS_Launcher',
)
