#!/usr/bin/env python3
"""
Debug Script for Title Field Detection
Tests all title field detection methods and shows what's on the page
"""

import logging
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

logger = logging.getLogger(__name__)

def test_title_field_detection():
    """
    Debug title field detection - requires an active browser session
    """

    print("=" * 70)
    print("TITLE FIELD DETECTION - DEBUG MODE")
    print("=" * 70)
    print()
    print("⚠️  IMPORTANT: This script requires:")
    print("   1. ixBrowser profile already open")
    print("   2. Facebook Reel upload page loaded")
    print("   3. Upload interface visible (after clicking 'Add Videos')")
    print()
    print("=" * 70)
    print()

    # Try to import Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
    except ImportError:
        print("❌ Selenium not installed!")
        print("   Install: pip install selenium")
        return False

    print("Step 1: Enter the debugging port")
    print("   (Usually: 9222 or check ixBrowser settings)")
    port = input("   Port number: ").strip() or "9222"

    try:
        # Connect to existing Chrome instance
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")

        print(f"\nStep 2: Connecting to Chrome on port {port}...")
        driver = webdriver.Chrome(options=chrome_options)
        print("✅ Connected successfully!")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("   1. Is ixBrowser open?")
        print("   2. Is remote debugging enabled?")
        print("   3. Check the port number")
        return False

    try:
        # Get current URL
        current_url = driver.current_url
        print(f"\n✅ Current URL: {current_url}")

        if "facebook.com" not in current_url:
            print("⚠️  Warning: Not on Facebook!")
            print("   Please navigate to a Facebook Reel upload page first.")

        print("\n" + "=" * 70)
        print("SEARCHING FOR TITLE FIELDS...")
        print("=" * 70)

        # Define all selectors
        title_selectors = [
            ("//input[@placeholder='Add a title to your reel']", "Reel title placeholder"),
            ("//input[@placeholder='Title']", "Generic title placeholder"),
            ("//input[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'title')]", "Title (case-insensitive)"),
            ("//input[contains(@aria-label, 'Title') or contains(@aria-label, 'title')]", "Title aria-label"),
            ("//input[@name='title']", "Title name attribute"),
            ("//div[contains(@class, 'title')]//input", "Title in div class"),
            ("//textarea[@placeholder='Describe your reel...']", "Description (Reel)"),
            ("//textarea[contains(@placeholder, 'describe your reel')]", "Description (contains)"),
        ]

        found_count = 0

        for idx, (selector, name) in enumerate(title_selectors, 1):
            print(f"\n[{idx}] Testing: {name}")
            print(f"    XPath: {selector}")

            try:
                elements = driver.find_elements(By.XPATH, selector)

                if not elements:
                    print("    Result: ❌ Not found")
                else:
                    print(f"    Result: ✅ Found {len(elements)} element(s)")

                    for elem_idx, elem in enumerate(elements, 1):
                        try:
                            is_visible = elem.is_displayed()
                            placeholder = elem.get_attribute("placeholder") or "(none)"
                            aria_label = elem.get_attribute("aria-label") or "(none)"
                            value = elem.get_attribute("value") or "(empty)"
                            tag = elem.tag_name

                            print(f"\n    Element {elem_idx}:")
                            print(f"      Tag: {tag}")
                            print(f"      Visible: {'YES' if is_visible else 'NO'}")
                            print(f"      Placeholder: {placeholder}")
                            print(f"      Aria-label: {aria_label}")
                            print(f"      Current value: {value}")

                            if is_visible:
                                found_count += 1
                                print(f"      ✅ THIS FIELD CAN BE USED!")
                        except Exception as e:
                            print(f"      Error accessing element: {e}")

            except Exception as e:
                print(f"    Error: {e}")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total visible title fields found: {found_count}")

        if found_count == 0:
            print("\n❌ NO TITLE FIELDS FOUND!")
            print("\nPossible reasons:")
            print("   1. Upload interface not loaded yet")
            print("   2. Different Facebook UI version")
            print("   3. Field has different placeholder text")
            print("\nLet me search for ALL input/textarea fields...")

            # Search all inputs
            all_inputs = driver.find_elements(By.XPATH, "//input[@type='text'] | //textarea")
            print(f"\nFound {len(all_inputs)} total text input/textarea fields:")

            for idx, inp in enumerate(all_inputs[:10], 1):  # Show first 10
                try:
                    if inp.is_displayed():
                        placeholder = inp.get_attribute("placeholder") or "(none)"
                        aria_label = inp.get_attribute("aria-label") or "(none)"
                        tag = inp.tag_name
                        print(f"\n{idx}. <{tag}>")
                        print(f"   Placeholder: {placeholder}")
                        print(f"   Aria-label: {aria_label}")
                except:
                    pass

            if len(all_inputs) > 10:
                print(f"\n... and {len(all_inputs) - 10} more fields")

        else:
            print(f"\n✅ Found {found_count} usable field(s)")
            print("   Title detection should work!")

        print("\n" + "=" * 70)

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Don't close the driver - it's attached to existing browser
        pass

    return True

if __name__ == "__main__":
    try:
        test_title_field_detection()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
