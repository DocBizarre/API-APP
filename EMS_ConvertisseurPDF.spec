# -*- mode: python ; coding: utf-8 -*-
# Build allégé : pdfplumber, WeasyPrint, PIL et pypdf restent sur le serveur.
# Le .exe n'embarque que Tkinter (stdlib) + requests.

a = Analysis(
    ['convertisseurpdf.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'requests',
        'configparser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'weasyprint', 'pdfplumber', 'pdfminer',
        'pypdf', 'PIL', 'Pillow',
        'pydyf', 'tinyhtml5', 'cssselect2', 'tinycss2',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EMS_ConvertisseurPDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['favicon.ico'],
)
