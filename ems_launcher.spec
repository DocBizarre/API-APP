# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['ems_launcher.py'],
    pathex=[SPECPATH, os.path.join(SPECPATH, 'ems_project'), os.path.join(SPECPATH, 'garanties_app'), os.path.join(SPECPATH, 'amelioration_app'), os.path.join(SPECPATH, 'BI_app'), os.path.join(SPECPATH, 'pieces_app')],
    binaries=[],
    datas=[('config.ini', '.'), ('BI_app\\ems_bi.html', 'BI_app')],
    hiddenimports=['ems_client.api', 'ems_client.sync_config', 'ems_client.sync_client', 'shared.bon_generator', 'shared.mailer', 'shared.logo_data', 'shared.garantie_generator', 'shared.amelioration_generator', 'shared.csv_importer', 'app_garanties', 'app_amelioration', 'app_bi'],
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
    name='EMS_Launcher',
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
