# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['pieces_app\\app_pieces.py'],
    pathex=['C:\\Users\\Stagiaire.be\\Desktop\\APP API'],
    binaries=[],
    datas=[('config.ini', '.')],
    hiddenimports=['ems_client.api', 'ems_client.sync_config'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='EMS_Pieces',
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
