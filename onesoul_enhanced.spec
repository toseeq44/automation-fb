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

# Cloudflared
if os.path.exists('cloudflared.exe'):
    optional_binaries.append(('cloudflared.exe', '.'))
    print("✓ cloudflared.exe found")
else:
    print("⚠️  WARNING: cloudflared.exe not found - skipping")

# FFmpeg binaries (CRITICAL for video editing)
if os.path.exists('ffmpeg/ffmpeg.exe'):
    optional_binaries.append(('ffmpeg/ffmpeg.exe', 'ffmpeg'))
    print("✓ ffmpeg.exe found")
else:
    print("⚠️  WARNING: ffmpeg/ffmpeg.exe not found - video editing will NOT work in EXE")

if os.path.exists('ffmpeg/ffprobe.exe'):
    optional_binaries.append(('ffmpeg/ffprobe.exe', 'ffmpeg'))
    print("✓ ffprobe.exe found")
else:
    print("⚠️  WARNING: ffmpeg/ffprobe.exe not found")

# yt-dlp binary
if os.path.exists('bin/yt-dlp.exe'):
    optional_binaries.append(('bin/yt-dlp.exe', 'bin'))
    print("✓ yt-dlp.exe found")
else:
    print("⚠️  WARNING: bin/yt-dlp.exe not found - link grabber may not work")

# Optional data files - only include if they exist
optional_datas = []

# Note: ffmpeg binaries are now added to optional_binaries above
# We don't need to include the entire directory, just the exe files

# Check for presets
if os.path.exists('presets') and os.path.isdir('presets'):
    optional_datas.append(('presets', 'presets'))
    print("✓ presets directory found")
else:
    print("⚠️  WARNING: presets directory not found")

# Check for MediaPipe models (for AR features)
try:
    import mediapipe
    import site
    # Find MediaPipe installation path
    mp_path = None
    for site_path in site.getsitepackages():
        potential_path = os.path.join(site_path, 'mediapipe', 'modules')
        if os.path.exists(potential_path):
            mp_path = potential_path
            break

    if mp_path:
        optional_datas.append((mp_path, 'mediapipe/modules'))
        print("✓ MediaPipe models found - AR features will be available")
    else:
        print("⚠️  WARNING: MediaPipe models not found - AR features may not work")
except ImportError:
    print("⚠️  WARNING: MediaPipe not installed - AR features disabled")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=optional_binaries,  # Use dynamic binaries list
    datas=[
        # Helper images for auto uploader (REQUIRED - image recognition)
        ('modules/auto_uploader/helper_images/*.png', 'modules/auto_uploader/helper_images'),

        # Creator shortcuts and data (for IXBrowser/GoLogin)
        ('modules/auto_uploader/creator_shortcuts', 'modules/auto_uploader/creator_shortcuts'),
        ('modules/auto_uploader/creators', 'modules/auto_uploader/creators'),
        ('modules/auto_uploader/data', 'modules/auto_uploader/data'),

        # NOTE: ix_data is NOT included - it's a runtime workspace created automatically

        # Chromium browser data files (for NST browser approach)
        ('bin/chromium', 'bin/chromium'),

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

        # AR Face Effects (NEW - MediaPipe)
        'mediapipe',
        'mediapipe.python',
        'mediapipe.python.solutions',
        'mediapipe.python.solutions.face_mesh',
        'mediapipe.python.solutions.drawing_utils',
        'mediapipe.python.solutions.drawing_styles',
        'google.protobuf',  # Required by MediaPipe
        'protobuf',
        
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
    upx=False,  # UPX disabled to prevent antivirus false positives
    console=False,  # No console window (GUI mode)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui-redesign/assets/onesoul_logo.ico',  # Application icon
    version='version_info.txt',  # CRITICAL: Version info prevents antivirus false positives
    manifest='manifest.xml',  # Windows manifest for compatibility and proper execution
    uac_admin=False,  # Don't require admin privileges (prevents UAC prompt)
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
