# -*- mode: python ; coding: utf-8 -*-

"""
OneSoul PyInstaller Spec File
Comprehensive configuration for bundling all dependencies
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        ('cloudflared.exe', '.'),
        ('bin/yt-dlp.exe', 'bin'),  # yt-dlp binary for Link Grabber
    ],
    datas=[
        # Helper images for auto uploader
        ('modules/auto_uploader/helper_images/*.png', 'modules/auto_uploader/helper_images'),
        ('modules/auto_uploader/creator_shortcuts', 'modules/auto_uploader/creator_shortcuts'),
        ('modules/auto_uploader/creators', 'modules/auto_uploader/creators'),
        ('modules/auto_uploader/data', 'modules/auto_uploader/data'),
        ('modules/auto_uploader/ix_data', 'modules/auto_uploader/ix_data'),

        
        # GUI assets (new design)
        ('gui-redesign/assets/*.html', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.svg', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.ico', 'gui-redesign/assets'),
        
        # Include presets folder if exists
        ('presets', 'presets'),

        # FFMPEG
        ('ffmpeg', 'ffmpeg'),

        # Configs to bundle
        ('api_config.json', '.'),
    ],
    hiddenimports=[
        # PyQt5 essentials
        'PyQt5.sip',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        
        # Video downloader dependencies
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',
        
        # HTTP and networking
        'requests',
        'urllib3',
        'certifi',
        
        # Cookies and authentication
        'browser_cookie3',
        'cryptography',
        'cryptography.fernet',
        
        # Video editor dependencies
        'moviepy',
        'moviepy.video',
        'moviepy.audio',
        'moviepy.editor',
        'imageio',
        'imageio_ffmpeg',
        'numpy',
        'scipy',
        'PIL',
        'pillow',
        
        # Browser automation
        'pyautogui',
        'pygetwindow',
        'opencv-python',
        'cv2',
        'psutil',
        
        # License system
        'json',
        'hashlib',
        'hmac',
        'base64',
        
        # API Manager
        'google.auth',
        'googleapiclient',
        'googleapiclient.discovery',
        
        # Instagram
        'instaloader',
        
        # Parsing
        'beautifulsoup4',
        'bs4',
        'lxml',
        'lxml.etree',
        
        # Utilities
        'pyperclip',
        'pathlib',
        
        # Logging
        'logging',
        'logging.handlers',
        
        # Config
        'modules.config',
        'modules.config.config_manager',
        'modules.config.utils',
        
        # All major modules
        'modules.api_manager',
        'modules.auto_uploader',
        'modules.license',
        'modules.link_grabber',
        'modules.logging',
        'modules.metadata_remover',
        'modules.ui',
        'modules.video_downloader',
        'modules.video_editor',
        'modules.workflows',
        'modules.cookies_manager',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'server',  # Exclude server folder (separate app)
        'instance',
        'test_*',  # Exclude test files
        '_pytest',
        'pytest',
    ],
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
    console=False,  # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui-redesign/assets/onesoul_logo.ico',
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
