# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['ems_launcher.py'],
    pathex=[SPECPATH, os.path.join(SPECPATH, 'ems_project'), os.path.join(SPECPATH, 'garanties_app'), os.path.join(SPECPATH, 'amelioration_app'), os.path.join(SPECPATH, 'BI_app'), os.path.join(SPECPATH, 'pieces_app')],
    binaries=[],
    datas=[('config.ini', '.'), ('BI_app\\ems_bi.html', 'BI_app')],
    hiddenimports=['ems_client.api', 'ems_client.sync_config', 'ems_client.sync_client', 'shared.bon_generator', 'shared.logo_data', 'shared.updater'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # main/app_pieces/app_garanties/app_amelioration/app_bi/convertisseurpdf ne servent
    # qu'au mode developpement non fige (_demarrar_app avec multiprocessing) : en .exe,
    # _lancer() ne fait que subprocess.Popen() vers les .exe separes, jamais ces imports.
    # PyInstaller les detecte quand meme par analyse statique de _demarrar_app() et
    # embarque leurs dependances lourdes (weasyprint/GTK, openpyxl, pdfplumber/pdfminer,
    # et via une dependance tierce du venv global : pandas/scipy/torch/torchvision/pytest,
    # sans rapport avec EMS) - d'ou un Launcher a 260 Mo, tres long a s'auto-extraire.
    excludes=['main', 'app_pieces', 'app_garanties', 'app_amelioration', 'app_bi',
              'convertisseurpdf', 'weasyprint', 'openpyxl', 'pdfplumber', 'pdfminer',
              'pandas', 'scipy', 'torch', 'torchvision', 'torchmetrics', 'pytest'],
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
    upx=False,
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
