"""
Facebook Upload Bot - Setup and Testing Script
Helps verify configuration and test browser connectivity
"""

import os
import sys
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils import ConfigLoader, DatabaseManager
from browser_controller import BrowserController


class SetupWizard:
    """Interactive setup wizard"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.checks_passed = []
        self.checks_failed = []

    def run(self):
        """Run setup wizard"""
        self.print_header()

        print("\n🔍 Running system checks...\n")

        # Run checks
        self.check_python_version()
        self.check_folder_structure()
        self.check_config_file()
        self.check_dependencies()
        self.check_creator_setup()
        self.check_browser_installation()

        # Print results
        self.print_results()

        # Offer tests
        if self.checks_failed:
            print("\n⚠️  Please fix the issues above before proceeding")
        else:
            print("\n✅ All checks passed!")
            self.offer_tests()

    def print_header(self):
        """Print setup header"""
        print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          Facebook Upload Bot - Setup Wizard              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
        """)

    def check_python_version(self):
        """Check Python version"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            self.checks_passed.append(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        else:
            self.checks_failed.append(f"✗ Python version too old ({version.major}.{version.minor}). Need 3.8+")

    def check_folder_structure(self):
        """Check required folders exist"""
        required_folders = [
            'config',
            'creators',
            'creator_shortcuts',
            'logs'
        ]

        for folder in required_folders:
            path = self.base_dir / folder
            if path.exists():
                self.checks_passed.append(f"✓ Folder: {folder}/")
            else:
                path.mkdir(parents=True, exist_ok=True)
                self.checks_passed.append(f"✓ Created folder: {folder}/")

    def check_config_file(self):
        """Check config file"""
        config_file = self.base_dir / 'config' / 'settings.json'

        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                self.checks_passed.append("✓ Config file: config/settings.json")
            except json.JSONDecodeError as e:
                self.checks_failed.append(f"✗ Config file has invalid JSON: {e}")
        else:
            self.checks_failed.append("✗ Config file not found: config/settings.json")

    def check_dependencies(self):
        """Check Python dependencies"""
        required_packages = [
            ('selenium', 'selenium'),
            ('pyautogui', 'pyautogui'),
            ('pygetwindow', 'pygetwindow'),
            ('PIL', 'pillow')
        ]

        for import_name, package_name in required_packages:
            try:
                __import__(import_name)
                self.checks_passed.append(f"✓ Package: {package_name}")
            except ImportError:
                self.checks_failed.append(f"✗ Missing package: {package_name} (run: pip install {package_name})")

    def check_creator_setup(self):
        """Check if creators are set up"""
        creators_dir = self.base_dir / 'creators'
        shortcuts_dir = self.base_dir / 'creator_shortcuts'

        # Check creators
        creators = [d for d in creators_dir.iterdir() if d.is_dir()]
        if creators:
            self.checks_passed.append(f"✓ Found {len(creators)} creator folder(s)")
        else:
            self.checks_failed.append("✗ No creator folders found in creators/")

        # Check shortcuts
        browser_types = [d for d in shortcuts_dir.iterdir() if d.is_dir()]
        if browser_types:
            total_accounts = 0
            for browser_type in browser_types:
                accounts = [d for d in browser_type.iterdir() if d.is_dir()]
                total_accounts += len(accounts)

            self.checks_passed.append(f"✓ Found {total_accounts} browser account(s)")
        else:
            self.checks_failed.append("✗ No browser accounts found in creator_shortcuts/")

    def check_browser_installation(self):
        """Check if browsers are installed"""
        # This is a basic check - actual installation varies
        print("\n📋 Browser Installation Check:")
        print("   Please verify manually that you have installed:")
        print("   - GoLogin (https://gologin.com/) OR")
        print("   - Incogniton (https://incogniton.com/)")
        print("")

    def print_results(self):
        """Print check results"""
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)

        for check in self.checks_passed:
            print(check)

        if self.checks_failed:
            print("\n❌ FAILED CHECKS:")
            for check in self.checks_failed:
                print(check)

        print(f"\nTotal: {len(self.checks_passed)} passed, {len(self.checks_failed)} failed")
        print("="*60)

    def offer_tests(self):
        """Offer to run tests"""
        print("\n🧪 Available Tests:")
        print("   1. Test browser launch")
        print("   2. Test Selenium connection")
        print("   3. Test database")
        print("   4. Show configuration")
        print("   5. Exit")

        choice = input("\nSelect test (1-5): ").strip()

        if choice == '1':
            self.test_browser_launch()
        elif choice == '2':
            self.test_selenium_connection()
        elif choice == '3':
            self.test_database()
        elif choice == '4':
            self.show_configuration()
        elif choice == '5':
            print("\n👋 Setup wizard complete!")
            return
        else:
            print("Invalid choice")

        # Offer again
        self.offer_tests()

    def test_browser_launch(self):
        """Test browser launch"""
        print("\n🚀 Testing Browser Launch...")

        config = ConfigLoader(str(self.base_dir / 'config' / 'settings.json'))
        browser_controller = BrowserController(config)

        print("\n   Available browsers:")
        browsers = config.get('browsers', {})
        for idx, (browser_type, browser_config) in enumerate(browsers.items(), 1):
            enabled = browser_config.get('enabled', True)
            status = "✓" if enabled else "✗"
            print(f"   {idx}. {status} {browser_type.upper()}")

        choice = input("\n   Select browser (1-2): ").strip()

        browser_types = list(browsers.keys())
        if choice.isdigit() and 1 <= int(choice) <= len(browser_types):
            browser_type = browser_types[int(choice) - 1]

            print(f"\n   Launching {browser_type}...")
            result = browser_controller.launch_browser(browser_type)

            if result:
                print(f"   ✅ {browser_type} launched successfully!")
                input("   Press Enter to continue...")
                browser_controller.close_browser(browser_type)
            else:
                print(f"   ❌ Failed to launch {browser_type}")
        else:
            print("   Invalid choice")

    def test_selenium_connection(self):
        """Test Selenium connection"""
        print("\n🔗 Testing Selenium Connection...")
        print("   Make sure your browser is running with remote debugging enabled")

        config = ConfigLoader(str(self.base_dir / 'config' / 'settings.json'))
        browser_controller = BrowserController(config)

        browsers = config.get('browsers', {})
        for idx, browser_type in enumerate(browsers.keys(), 1):
            print(f"   {idx}. {browser_type.upper()}")

        choice = input("\n   Select browser (1-2): ").strip()
        browser_types = list(browsers.keys())

        if choice.isdigit() and 1 <= int(choice) <= len(browser_types):
            browser_type = browser_types[int(choice) - 1]

            print(f"\n   Connecting to {browser_type}...")
            driver = browser_controller.connect_selenium(browser_type)

            if driver:
                print(f"   ✅ Connected successfully!")
                print(f"   Current URL: {driver.current_url}")
                input("   Press Enter to close connection...")
                driver.quit()
            else:
                print(f"   ❌ Connection failed")
                print(f"   Make sure:")
                print(f"   1. {browser_type} is running")
                print(f"   2. Remote debugging is enabled")
        else:
            print("   Invalid choice")

    def test_database(self):
        """Test database"""
        print("\n💾 Testing Database...")

        try:
            db = DatabaseManager(str(self.base_dir / 'config' / 'upload_status.db'))
            print("   ✅ Database initialized successfully")

            # Test insert
            browser_id = db.get_or_create_browser_account('test', 'test_account')
            print(f"   ✅ Created test browser account (ID: {browser_id})")

            db.close()
            print("   ✅ Database test passed")

        except Exception as e:
            print(f"   ❌ Database test failed: {e}")

    def show_configuration(self):
        """Show current configuration"""
        print("\n⚙️  Current Configuration:")

        config_file = self.base_dir / 'config' / 'settings.json'

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            print("\n   Browsers:")
            for browser_type, browser_config in config.get('browsers', {}).items():
                enabled = "✓" if browser_config.get('enabled', True) else "✗"
                print(f"     {enabled} {browser_type}: Port {browser_config.get('debug_port')}")

            print("\n   Upload Settings:")
            upload_settings = config.get('upload_settings', {})
            print(f"     Wait after upload: {upload_settings.get('wait_after_upload', 30)}s")
            print(f"     Wait between videos: {upload_settings.get('wait_between_videos', 120)}s")
            print(f"     Delete after upload: {upload_settings.get('delete_after_upload', False)}")
            print(f"     Skip uploaded: {upload_settings.get('skip_uploaded', True)}")

            print("\n   Paths:")
            paths = config.get('paths', {})
            for key, value in paths.items():
                print(f"     {key}: {value}")

        except Exception as e:
            print(f"   ❌ Error reading config: {e}")


def main():
    """Main entry point"""
    wizard = SetupWizard()
    wizard.run()


if __name__ == "__main__":
    main()
