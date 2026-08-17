# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('selenium')
hiddenimports += collect_submodules('webdriver_manager')

excluded_heavy_modules = [
    'cv2',
    'IPython',
    'matplotlib',
    'pytest',
    'scipy',
    'sklearn',
    'tensorflow',
    'torch',
]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates\\index.html', 'templates'), ('static\\style.css', 'static'), ('static\\app.js', 'static'), ('scraper.py', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_heavy_modules,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AmazonASINDashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AmazonASINDashboard',
)
