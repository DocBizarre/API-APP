# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['ems_project\\app_parc.py'],
    pathex=[SPECPATH, os.path.join(SPECPATH, 'ems_project')],
    binaries=[],
    datas=[('config.ini', '.')],
    hiddenimports=['ems_client.api', 'ems_client.sync_config', 'ems_client.sync_client', 'shared.bon_generator', 'shared.mailer', 'shared.logo_data', 'shared.amelioration_generator', 'shared.garantie_generator', 'shared.csv_importer'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['weasyprint', 'pydyf', 'tinyhtml5'],
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
    name='EMS_Parc',
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
