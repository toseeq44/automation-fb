# -*- mode: python ; coding: utf-8 -*-

"""
OneSoul PyInstaller Spec File
Comprehensive configuration for bundling all dependencies

IMPORTANT: Before building, ensure these files exist:
- cloudflared.exe (in root directory)
- ffmpeg/ffmpeg.exe and ffmpeg/ffprobe.exe
"""

import os
from pathlib import Path

block_cipher = None

# Optional binaries - only include if they exist
optional_binaries = []
if os.path.exists('cloudflared.exe'):
    optional_binaries.append(('cloudflared.exe', '.'))
else:
    print("⚠️  WARNING: cloudflared.exe not found - skipping")

# Optional data files - only include if they exist
optional_datas = []

# Check for ffmpeg
if os.path.exists('ffmpeg') and os.path.isdir('ffmpeg'):
    optional_datas.append(('ffmpeg', 'ffmpeg'))
    print("✓ ffmpeg directory found")
else:
    print("⚠️  WARNING: ffmpeg directory not found - video editing may not work")

# Check for presets
if os.path.exists('presets') and os.path.isdir('presets'):
    optional_datas.append(('presets', 'presets'))
    print("✓ presets directory found")
else:
    print("⚠️  WARNING: presets directory not found")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=optional_binaries,
    datas=[
        # Helper images for auto uploader (REQUIRED - image recognition)
        ('modules/auto_uploader/helper_images/*.png', 'modules/auto_uploader/helper_images'),

        # Creator shortcuts and data (for IXBrowser/GoLogin)
        ('modules/auto_uploader/creator_shortcuts', 'modules/auto_uploader/creator_shortcuts'),
        ('modules/auto_uploader/creators', 'modules/auto_uploader/creators'),
        ('modules/auto_uploader/data', 'modules/auto_uploader/data'),

        # NOTE: ix_data is NOT included - it's a runtime workspace created automatically

        # GUI assets (new design)
        ('gui-redesign/assets/*.html', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.svg', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.ico', 'gui-redesign/assets'),

        # Configs to bundle
        ('api_config.json', '.'),
    ] + optional_datas,  # Add optional data files
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
