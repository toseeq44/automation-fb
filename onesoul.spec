# -*- mode: python ; coding: utf-8 -*-
"""
OneSoul Pro - PyInstaller Spec File
========================================

This spec file bundles:
- All Python dependencies
- FFmpeg executable
- Helper images for Auto Uploader
- Configuration files
- Resources and assets

Usage:
    pyinstaller contentflow.spec

Or use the build script:
    python build_exe.py
"""

import os
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(SPECPATH).resolve()

# Application info
APP_NAME = 'OneSoul Pro'
APP_VERSION = '2.0.0'
MAIN_SCRIPT = 'main.py'

# ═══════════════════════════════════════════════════════════
# DATA FILES TO BUNDLE
# ═══════════════════════════════════════════════════════════

# Helper images for Auto Uploader UI detection
helper_images = []
helper_images_path = PROJECT_ROOT / 'modules' / 'auto_uploader' / 'helper_images'
if helper_images_path.exists():
    for img in helper_images_path.glob('*.png'):
        helper_images.append((str(img), 'modules/auto_uploader/helper_images'))

# GUI icons and assets (from gui-redesign/assets/)
gui_assets = []
gui_redesign_assets_path = PROJECT_ROOT / 'gui-redesign' / 'assets'
if gui_redesign_assets_path.exists():
    for asset in gui_redesign_assets_path.rglob('*'):
        if asset.is_file():
            # Keep the relative path structure: gui-redesign/assets/filename
            rel_path = asset.relative_to(PROJECT_ROOT).parent
            gui_assets.append((str(asset), str(rel_path)))

# Also check for assets/ folder if exists
assets_path = PROJECT_ROOT / 'assets'
if assets_path.exists():
    for asset in assets_path.rglob('*'):
        if asset.is_file():
            rel_path = asset.relative_to(PROJECT_ROOT).parent
            gui_assets.append((str(asset), str(rel_path)))

# Data files for Auto Uploader
auto_uploader_data = []
au_data_path = PROJECT_ROOT / 'modules' / 'auto_uploader' / 'data_files'
if au_data_path.exists():
    for f in au_data_path.glob('*'):
        if f.is_file():
            auto_uploader_data.append((str(f), 'modules/auto_uploader/data_files'))

# Config templates
config_files = []
config_path = PROJECT_ROOT / 'data_files'
if config_path.exists():
    for f in config_path.glob('*.json'):
        config_files.append((str(f), 'data_files'))

# Combine all data files
datas = helper_images + gui_assets + auto_uploader_data + config_files

# Add FFmpeg if exists in project
ffmpeg_path = PROJECT_ROOT / 'ffmpeg' / 'ffmpeg.exe'
if ffmpeg_path.exists():
    datas.append((str(ffmpeg_path), 'ffmpeg'))
    ffprobe_path = PROJECT_ROOT / 'ffmpeg' / 'ffprobe.exe'
    if ffprobe_path.exists():
        datas.append((str(ffprobe_path), 'ffmpeg'))

# ═══════════════════════════════════════════════════════════
# HIDDEN IMPORTS
# ═══════════════════════════════════════════════════════════

hiddenimports = [
    # PyQt5
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.sip',

    # Video/Media processing
    'yt_dlp',
    'moviepy',
    'moviepy.editor',
    'moviepy.video',
    'moviepy.video.io',
    'moviepy.video.io.ffmpeg_tools',
    'cv2',
    'PIL',
    'PIL.Image',

    # Automation
    'pyautogui',
    'pygetwindow',
    'pyscreeze',

    # Cryptography for license
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.kdf.pbkdf2',

    # Network/Web
    'requests',
    'urllib3',
    'selenium',

    # Data handling
    'json',
    'hashlib',
    'hmac',
    'base64',

    # System
    'uuid',
    'platform',
    'subprocess',
    'threading',

    # Project modules
    'modules',
    'modules.license',
    'modules.license.secure_license',
    'modules.video_downloader',
    'modules.video_editor',
    'modules.link_grabber',
    'modules.auto_uploader',
    'modules.ui',
    'modules.logging',
    'modules.config',
]

# ═══════════════════════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════════════════════

block_cipher = None

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',  # Not needed
        'test',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ═══════════════════════════════════════════════════════════
# PYZ (Python Archive)
# ═══════════════════════════════════════════════════════════

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ═══════════════════════════════════════════════════════════
# EXE (Executable)
# ═══════════════════════════════════════════════════════════

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OneSoulPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress executable
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'assets' / 'icon.ico') if (PROJECT_ROOT / 'assets' / 'icon.ico').exists() else None,
)
