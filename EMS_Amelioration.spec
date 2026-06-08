# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['amelioration_app\\app_amelioration.py'],
    pathex=[SPECPATH, os.path.join(SPECPATH, 'amelioration_app')],
    binaries=[],
    datas=[('config.ini', '.')],
    hiddenimports=['ems_client.api', 'ems_client.sync_config', 'ems_client.sync_client', 'shared.amelioration_generator', 'shared.bon_generator', 'shared.logo_data'],
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
    name='EMS_Amelioration',
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
