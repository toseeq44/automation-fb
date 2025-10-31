"""
Simple dependency installer for Facebook Auto Uploader
Run this to install all required packages
"""

import subprocess
import sys
from pathlib import Path


def install_dependencies():
    """Install all required dependencies"""
    print("=" * 60)
    print("Facebook Auto Uploader - Dependency Installer")
    print("=" * 60)
    print()

    # Get requirements file path
    requirements_file = Path(__file__).parent / 'requirements.txt'

    if not requirements_file.exists():
        print("❌ Error: requirements.txt not found!")
        return False

    print("📦 Installing dependencies from requirements.txt...")
    print()

    try:
        # Install using pip
        subprocess.check_call([
            sys.executable,
            '-m',
            'pip',
            'install',
            '-r',
            str(requirements_file)
        ])

        print()
        print("=" * 60)
        print("✅ All dependencies installed successfully!")
        print("=" * 60)
        print()
        print("You can now use the Facebook Auto Uploader.")
        print()
        return True

    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print("❌ Installation failed!")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Try running manually:")
        print(f"  pip install -r {requirements_file}")
        print()
        return False


def check_dependencies():
    """Check if dependencies are installed"""
    print("🔍 Checking dependencies...")
    print()

    dependencies = {
        'selenium': 'Selenium WebDriver',
        'webdriver_manager': 'WebDriver Manager',
        'pyautogui': 'PyAutoGUI (Windows automation)',
        'pygetwindow': 'PyGetWindow (Windows automation)',
        'PIL': 'Pillow (Image processing)'
    }

    missing = []
    installed = []

    for module, name in dependencies.items():
        try:
            __import__(module)
            installed.append(name)
            print(f"  ✓ {name}")
        except ImportError:
            missing.append(name)
            print(f"  ✗ {name} - NOT INSTALLED")

    print()

    if missing:
        print(f"❌ Missing {len(missing)} package(s)")
        print("Run this script to install them.")
        return False
    else:
        print(f"✅ All {len(installed)} dependencies are installed!")
        return True


if __name__ == "__main__":
    print()

    # First check what's installed
    all_installed = check_dependencies()

    if not all_installed:
        print()
        response = input("Install missing dependencies? (y/n): ").strip().lower()

        if response == 'y':
            print()
            install_dependencies()
        else:
            print("Installation cancelled.")
    else:
        print("No installation needed.")

    print()
