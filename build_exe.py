"""
ContentFlow Pro - Build Script
===============================

This script builds the Windows EXE distribution:
1. Checks/installs required dependencies
2. Downloads FFmpeg if not present
3. Runs PyInstaller to create the EXE
4. Creates the final distribution package

Usage:
    python build_exe.py

Requirements:
    pip install pyinstaller

Output:
    dist/ContentFlowPro.exe
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_ROOT / 'dist'
BUILD_DIR = PROJECT_ROOT / 'build'
FFMPEG_DIR = PROJECT_ROOT / 'ffmpeg'

# FFmpeg download URL (Windows 64-bit static build)
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_step(text):
    """Print a step indicator."""
    print(f"\n🔹 {text}")


def print_success(text):
    """Print a success message."""
    print(f"✅ {text}")


def print_warning(text):
    """Print a warning message."""
    print(f"⚠️  {text}")


def print_error(text):
    """Print an error message."""
    print(f"❌ {text}")


def check_pyinstaller():
    """Check if PyInstaller is installed."""
    print_step("Checking PyInstaller...")
    try:
        import PyInstaller
        print_success(f"PyInstaller {PyInstaller.__version__} found")
        return True
    except ImportError:
        print_warning("PyInstaller not found. Installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print_success("PyInstaller installed successfully")
            return True
        except Exception as e:
            print_error(f"Failed to install PyInstaller: {e}")
            return False


def download_ffmpeg():
    """Download FFmpeg if not present."""
    print_step("Checking FFmpeg...")

    ffmpeg_exe = FFMPEG_DIR / 'ffmpeg.exe'
    if ffmpeg_exe.exists():
        print_success("FFmpeg already present")
        return True

    print_warning("FFmpeg not found. Downloading...")

    try:
        # Create ffmpeg directory
        FFMPEG_DIR.mkdir(exist_ok=True)

        # Download FFmpeg
        zip_path = FFMPEG_DIR / 'ffmpeg.zip'
        print(f"   Downloading from: {FFMPEG_URL[:50]}...")

        # Use urllib to download
        urllib.request.urlretrieve(FFMPEG_URL, zip_path)

        print("   Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(FFMPEG_DIR)

        # Find and move the executables
        for root, dirs, files in os.walk(FFMPEG_DIR):
            for file in files:
                if file in ['ffmpeg.exe', 'ffprobe.exe']:
                    src = Path(root) / file
                    dst = FFMPEG_DIR / file
                    if src != dst:
                        shutil.move(str(src), str(dst))

        # Cleanup
        zip_path.unlink()
        # Remove extracted folder
        for item in FFMPEG_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)

        print_success("FFmpeg downloaded successfully")
        return True

    except Exception as e:
        print_error(f"Failed to download FFmpeg: {e}")
        print_warning("You can manually download FFmpeg from: https://ffmpeg.org/download.html")
        print_warning("Place ffmpeg.exe and ffprobe.exe in the 'ffmpeg' folder")
        return False


def clean_build():
    """Clean previous build artifacts."""
    print_step("Cleaning previous builds...")

    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"   Removed: {dir_path.name}/")

    print_success("Clean complete")


def run_pyinstaller():
    """Run PyInstaller with the spec file."""
    print_step("Building executable with PyInstaller...")

    spec_file = PROJECT_ROOT / 'contentflow.spec'

    if not spec_file.exists():
        print_error("contentflow.spec not found!")
        return False

    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"],
            cwd=str(PROJECT_ROOT),
            check=True
        )
        print_success("Build complete!")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"PyInstaller failed: {e}")
        return False


def verify_build():
    """Verify the build was successful."""
    print_step("Verifying build...")

    exe_path = DIST_DIR / 'ContentFlowPro.exe'

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print_success(f"Executable created: {exe_path}")
        print(f"   Size: {size_mb:.1f} MB")
        return True
    else:
        print_error("Executable not found!")
        return False


def create_distribution_package():
    """Create final distribution package."""
    print_step("Creating distribution package...")

    dist_package = DIST_DIR / 'ContentFlowPro_Distribution'
    dist_package.mkdir(exist_ok=True)

    # Copy EXE
    exe_src = DIST_DIR / 'ContentFlowPro.exe'
    if exe_src.exists():
        shutil.copy(exe_src, dist_package / 'ContentFlowPro.exe')

    # Create README
    readme_content = """
╔═══════════════════════════════════════════════════════════════════╗
║               CONTENTFLOW PRO - VIDEO AUTOMATION                  ║
║                        Version 2.0.0                              ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  📁 CONTENTS:                                                     ║
║     ContentFlowPro.exe - Main application                         ║
║                                                                   ║
║  🚀 HOW TO USE:                                                   ║
║     1. Double-click ContentFlowPro.exe                            ║
║     2. Copy your Hardware ID from the activation dialog           ║
║     3. Send Hardware ID to admin via WhatsApp                     ║
║     4. Receive and enter your license key                         ║
║     5. Enjoy ContentFlow Pro!                                     ║
║                                                                   ║
║  📋 PRICING:                                                      ║
║     BASIC: Rs 10,000/month (200 downloads/pages per day)          ║
║     PRO:   Rs 15,000/month (Unlimited)                            ║
║                                                                   ║
║  📞 CONTACT:                                                      ║
║     WhatsApp: 0307-7361139                                        ║
║                                                                   ║
║  ⚠️  NOTES:                                                       ║
║     - 1 license = 1 PC (Hardware bound)                           ║
║     - License cannot be transferred to another PC                 ║
║     - Daily limits reset at midnight                              ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""
    (dist_package / 'README.txt').write_text(readme_content.strip(), encoding='utf-8')

    print_success(f"Distribution package created: {dist_package}")

    # Create ZIP for easy sharing
    try:
        zip_path = DIST_DIR / 'ContentFlowPro_v2.0.0.zip'
        shutil.make_archive(
            str(zip_path.with_suffix('')),
            'zip',
            dist_package
        )
        zip_size = zip_path.stat().st_size / (1024 * 1024)
        print_success(f"ZIP package created: {zip_path.name} ({zip_size:.1f} MB)")
    except Exception as e:
        print_warning(f"Could not create ZIP: {e}")

    return True


# ═══════════════════════════════════════════════════════════
# MAIN BUILD PROCESS
# ═══════════════════════════════════════════════════════════

def main():
    """Main build process."""
    print_header("CONTENTFLOW PRO - BUILD SCRIPT")
    print(f"Project root: {PROJECT_ROOT}")

    # Step 1: Check PyInstaller
    if not check_pyinstaller():
        print_error("Cannot proceed without PyInstaller")
        return 1

    # Step 2: Download FFmpeg (optional but recommended)
    download_ffmpeg()

    # Step 3: Clean previous builds
    clean_build()

    # Step 4: Run PyInstaller
    if not run_pyinstaller():
        print_error("Build failed!")
        return 1

    # Step 5: Verify build
    if not verify_build():
        print_error("Build verification failed!")
        return 1

    # Step 6: Create distribution package
    create_distribution_package()

    # Done!
    print_header("BUILD COMPLETE!")
    print(f"""
📦 Output files:
   - dist/ContentFlowPro.exe
   - dist/ContentFlowPro_Distribution/
   - dist/ContentFlowPro_v2.0.0.zip

🚀 Next steps:
   1. Test the EXE on your machine
   2. Test on a clean Windows machine
   3. Share the ZIP file with users

⚠️  Remember:
   - Keep admin_license_generator.py PRIVATE!
   - Only distribute the EXE, not the source code
""")

    return 0


if __name__ == '__main__':
    sys.exit(main())
