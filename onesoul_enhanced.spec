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
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Optional binaries - only include if they exist
optional_binaries = []
if os.path.exists('cloudflared.exe'):
    optional_binaries.append(('cloudflared.exe', '.'))
else:
    print("WARNING: cloudflared.exe not found - skipping")

# Optional data files - only include if they exist
optional_datas = []

# Check for ffmpeg - bundle entire folder preserving bin/ structure
if os.path.exists('ffmpeg') and os.path.isdir('ffmpeg'):
    # Bundle ffmpeg/bin/* (exe + DLLs) into ffmpeg/bin/ so companion DLLs stay together
    if os.path.isdir(os.path.join('ffmpeg', 'bin')):
        optional_datas.append((os.path.join('ffmpeg', 'bin'), os.path.join('ffmpeg', 'bin')))
        print("INFO: ffmpeg/bin directory found (exe + DLLs will be bundled together)")
    else:
        optional_datas.append(('ffmpeg', 'ffmpeg'))
        print("INFO: ffmpeg directory found (flat structure)")
    # Also bundle presets if present inside ffmpeg
    if os.path.isdir(os.path.join('ffmpeg', 'presets')):
        optional_datas.append((os.path.join('ffmpeg', 'presets'), os.path.join('ffmpeg', 'presets')))
else:
    print("WARNING: ffmpeg directory not found - video editing/watermark/split WILL NOT WORK")

# Check for presets
if os.path.exists('presets') and os.path.isdir('presets'):
    optional_datas.append(('presets', 'presets'))
    print("INFO: presets directory found")
else:
    print("WARNING: presets directory not found")

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
        print("INFO: MediaPipe models found - AR features will be available")
    else:
        print("WARNING: MediaPipe models not found - AR features may not work")
except ImportError:
    print("WARNING: MediaPipe not installed - AR features disabled")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=optional_binaries + [
        ('bin/yt-dlp.exe', 'bin'),  # yt-dlp binary for Link Grabber
        ('bin/chromium/*', 'bin/chromium'),
    ],
    datas=[
        # Helper images for auto uploader (REQUIRED - image recognition)
        ('modules/auto_uploader/helper_images/*.png', 'modules/auto_uploader/helper_images'),

        # Creator shortcuts and data (for IXBrowser/GoLogin)
        ('modules/auto_uploader/creator_shortcuts', 'modules/auto_uploader/creator_shortcuts'),
        ('modules/auto_uploader/creators', 'modules/auto_uploader/creators'),
        ('modules/auto_uploader/data', 'modules/auto_uploader/data'),

        # NOTE: ix_data is NOT included - it's a runtime workspace created automatically

        # GUI assets (new design) - includes platform icons (.png)
        ('gui-redesign/assets/*.html', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.svg', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.ico', 'gui-redesign/assets'),
        ('gui-redesign/assets/*.png', 'gui-redesign/assets'),

        # Configs to bundle
        ('api_config.json', '.'),
    ] + optional_datas,  # Add optional data files
    hiddenimports=collect_submodules('encodings') + [
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
        'moviepy.video.fx',
        'moviepy.video.fx.all',
        'moviepy.video.io',
        'moviepy.video.io.VideoFileClip',
        'moviepy.audio',
        'moviepy.audio.fx',
        'moviepy.audio.fx.all',
        'moviepy.editor',
        'imageio',
        'imageio_ffmpeg',
        'imageio_ffmpeg._utils',
        'proglog',
        'decorator',
        'tqdm',
        'numpy',
        'scipy',
        'scipy.ndimage',
        'scipy.signal',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',

        # Browser automation - Selenium (CRITICAL for auto uploader)
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.common.action_chains',
        'selenium.webdriver.support',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.common',
        'selenium.common.exceptions',

        # Browser automation - UI control
        'pyautogui',
        'pygetwindow',
        'cv2',
        'psutil',

        # Windows COM API (pywin32) - for window management
        'win32gui',
        'win32con',
        'win32api',
        'pywintypes',
        'pythoncom',

        # AR Face Effects - MediaPipe
        'mediapipe',
        'mediapipe.python',
        'mediapipe.python.solutions',
        'mediapipe.python.solutions.face_mesh',
        'mediapipe.python.solutions.drawing_utils',
        'mediapipe.python.solutions.drawing_styles',
        'google.protobuf',
        'google.protobuf.descriptor',

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
        'bs4',
        'lxml',
        'lxml.etree',
        'lxml.html',

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
        'modules.creator_profiles',
        'modules.license',
        'modules.link_grabber',
        'modules.logging',
        'modules.metadata_remover',
        'modules.shared',
        'modules.title_generator',
        'modules.ui',
        'modules.video_downloader',
        'modules.video_editor',
        'modules.workflows',
        'modules.cookies_manager',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rth_clear_python_env.py'],
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
