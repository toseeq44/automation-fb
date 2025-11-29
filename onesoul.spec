# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('modules/auto_uploader/helper_images/*.png', 'modules/auto_uploader/helper_images'),
        ('gui-redesign/assets/*.html', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.svg', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.ico', 'gui-redesign/assets'),

    ],
    hiddenimports=[
        'PyQt5.sip',
        'PyQt5.QtWebEngineWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['server', 'instance'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OneSoul',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui-redesign/assets/onesoul_logo.ico',  # packaged app icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='OneSoul'
)
