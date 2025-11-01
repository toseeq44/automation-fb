"""Setup manager - Ask user for paths once, save them, reuse them."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Dict


class SetupManager:
    """
    Manage user paths setup.

    پہلی بار user سے paths پوچھتا ہے اور save کرتا ہے۔
    اگلی دفعہ saved paths استعمال کرتا ہے۔

    First time: Ask user for paths and save them
    Next time: Use saved paths automatically
    """

    # Setup file location
    SETUP_FILE = Path.home() / ".facebook_automation_setup.json"

    @classmethod
    def load_setup(cls) -> Optional[Dict[str, str]]:
        """
        لوڈ کریں saved setup اگر موجود ہے۔
        Load saved setup if it exists.

        Returns:
            Dictionary with paths or None if not setup yet
        """
        if cls.SETUP_FILE.exists():
            try:
                with open(cls.SETUP_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Could not load setup file: {e}")
                return None
        return None

    @classmethod
    def save_setup(cls, setup_data: Dict[str, str]) -> bool:
        """
        سیو کریں setup paths کو۔
        Save setup paths.

        Args:
            setup_data: Dictionary with paths

        Returns:
            True if saved successfully
        """
        try:
            with open(cls.SETUP_FILE, 'w', encoding='utf-8') as f:
                json.dump(setup_data, f, indent=2)
            logging.info(f"✓ Setup saved to: {cls.SETUP_FILE}")
            return True
        except Exception as e:
            logging.error(f"Could not save setup: {e}")
            return False

    @classmethod
    def ask_user_for_paths(cls) -> Dict[str, str]:
        """
        User سے پوچھیں کہاں login_data.txt ہے۔
        Ask user where login_data.txt file is located.

        Returns:
            Dictionary with login_data_path and other paths
        """
        print("\n" + "=" * 70)
        print("🔧 Facebook Automation Setup")
        print("=" * 70)
        print("\nیہ پہلی بار ہے۔ براہ کرم بتائیں کہاں آپ کی فائلیں ہیں۔")
        print("This is the first time setup. Please tell us where your files are.\n")

        # Ask for login_data.txt path
        print("1️⃣  login_data.txt فائل کہاں ہے؟")
        print("   Where is your login_data.txt file?")
        print("   (پوری path دیں - provide full path)")
        print("   Example: C:\\Users\\YourName\\Desktop\\data")
        print("   یا / or C:\\Users\\YourName\\Documents\n")

        while True:
            login_data_path = input("   Path: ").strip()

            if not login_data_path:
                print("   ❌ خالی نہیں ہو سکتا / Cannot be empty")
                continue

            login_data_file = Path(login_data_path) / "login_data.txt"

            # Check if path exists
            if not Path(login_data_path).exists():
                print(f"   ❌ یہ path موجود نہیں ہے / Path does not exist: {login_data_path}")
                continue

            # Check if login_data.txt exists
            if not login_data_file.exists():
                print(f"   ⚠️  login_data.txt یہاں نہیں ملی / Not found: {login_data_file}")
                create_choice = input("   کیا آپ یہ path استعمال کرنا چاہتے ہیں? / Use this path anyway? (y/n): ").strip().lower()
                if create_choice != 'y':
                    continue

            print(f"   ✓ محفوظ ہوگیا / Saved: {login_data_path}")
            break

        # Ask for browser shortcut location (optional)
        print("\n2️⃣  Browser shortcut کہاں ہے؟")
        print("   Where is your browser shortcut?")
        print("   (عام طور پر Desktop ہے / Usually Desktop)")
        print("   Default: C:\\Users\\YourName\\Desktop\n")

        desktop_path = input("   Path (یا Enter دیں default کے لیے / or press Enter for default): ").strip()

        if not desktop_path:
            desktop_path = str(Path.home() / "Desktop")
            print(f"   ✓ Default استعمال کیا / Using: {desktop_path}")
        elif not Path(desktop_path).exists():
            print(f"   ⚠️  Path موجود نہیں / Path does not exist, but will use anyway")

        # Save setup
        setup_data = {
            "login_data_path": login_data_path,
            "desktop_path": desktop_path,
            "setup_date": str(Path(login_data_path).stat().st_mtime),
        }

        if cls.save_setup(setup_data):
            print("\n✅ سیٹ اپ مکمل! / Setup Complete!")
            print(f"   login_data path: {login_data_path}")
            print(f"   Browser shortcut path: {desktop_path}")
        else:
            print("\n⚠️  سیٹ اپ محفوظ نہیں ہو سکی / Could not save setup")

        return setup_data

    @classmethod
    def get_paths(cls, force_setup: bool = False) -> Dict[str, str]:
        """
        حاصل کریں paths - پہلے saved سے، نہیں تو user سے پوچھیں۔
        Get paths - either from saved setup or ask user.

        Args:
            force_setup: اگر True تو دوبارہ سیٹ اپ کریں / Force re-setup

        Returns:
            Dictionary with all required paths
        """
        # Check if already setup
        if not force_setup:
            saved_setup = cls.load_setup()
            if saved_setup:
                logging.info("✓ Using saved setup from previous session")
                return saved_setup

        # First time or force setup
        logging.info("First time setup - asking user for paths")
        return cls.ask_user_for_paths()

    @classmethod
    def reset_setup(cls) -> None:
        """
        سیٹ اپ delete کریں اور دوبارہ سے پوچھیں۔
        Delete setup so user can reconfigure.
        """
        if cls.SETUP_FILE.exists():
            cls.SETUP_FILE.unlink()
            logging.info(f"✓ Setup reset. File deleted: {cls.SETUP_FILE}")
        else:
            logging.info("No setup file to delete")

    @classmethod
    def show_setup(cls) -> None:
        """
        اب کا سیٹ اپ دکھائیں۔
        Show current setup.
        """
        setup = cls.load_setup()
        if setup:
            print("\n" + "=" * 70)
            print("📋 Current Setup")
            print("=" * 70)
            for key, value in setup.items():
                print(f"  {key}: {value}")
            print("=" * 70 + "\n")
        else:
            print("\n⚠️  No setup configured yet\n")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # First time: Ask user
    paths = SetupManager.get_paths()
    print(f"\nGot paths: {paths}")

    # Next time: Use saved
    paths2 = SetupManager.get_paths()
    print(f"\nSecond time: {paths2}")

    # Show current setup
    SetupManager.show_setup()

    # Reset if needed
    # SetupManager.reset_setup()
