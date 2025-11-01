#!/usr/bin/env python3
"""
سادہ example - کیسے استعمال کریں۔
Simple example - How to use the new workflow.
"""

import logging
from modules.auto_uploader.facebook_steps import start_automation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

def main():
    """
    Main entry point.

    یہ وہی ہے جو GUI سے call ہوگا جب user "Start Upload" button دبائے۔
    This is what GUI will call when user clicks "Start Upload" button.
    """

    print("\n" + "=" * 70)
    print("📱 Facebook Upload Automation")
    print("=" * 70 + "\n")

    # پہلی بار: یہ setup پوچھے گا
    # First time: This will ask for setup
    # اگلی دفعہ: یہ saved paths استعمال کرے گا
    # Next time: This will use saved paths

    success = start_automation(force_setup=False)

    if success:
        print("\n" + "=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        print("Browser is ready, user is logged in.")
        print("Now you can upload content.\n")
        return True
    else:
        print("\n" + "=" * 70)
        print("❌ FAILED!")
        print("=" * 70)
        print("Check the error messages above.\n")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
