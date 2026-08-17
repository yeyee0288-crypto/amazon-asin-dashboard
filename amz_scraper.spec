# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules

selenium_hiddenimports = collect_submodules('selenium')
webdriver_manager_hiddenimports = collect_submodules('webdriver_manager')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates/index.html', 'templates'),
        ('static/style.css', 'static'),
        ('static/app.js', 'static'),
        ('scraper.py', '.'),
    ],
    hiddenimports=[
        'flask',
        'flask.templating',
        'jinja2',
        'openpyxl',
        'pandas',
        'queue',
        'selenium',
        'selenium.common',
        'selenium.common.exceptions',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'webdriver_manager',
        'webdriver_manager.chrome',
    ] + selenium_hiddenimports + webdriver_manager_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AmazonASINDashboard',
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
    icon=None,
)
