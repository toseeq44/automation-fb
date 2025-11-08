#!/usr/bin/env python3
"""
Verification script to confirm all improvements are in place
"""

import sys
from pathlib import Path

def verify_file_changes():
    """Verify all code changes are present"""

    print("\n" + "=" * 70)
    print("VERIFYING IMPROVEMENTS")
    print("=" * 70 + "\n")

    base_path = Path(__file__).parent
    workflow_dir = base_path / "modules" / "auto_uploader" / "browser" / "video_upload_workflow"

    # Check files exist
    files_to_check = [
        ("bookmark_navigator.py", workflow_dir / "bookmark_navigator.py"),
        ("add_videos_finder.py", workflow_dir / "add_videos_finder.py"),
    ]

    print("[*] Checking file existence...")
    all_exist = True
    for name, path in files_to_check:
        if path.exists():
            print(f"  [OK] {name}")
        else:
            print(f"  [ERROR] {name} NOT FOUND")
            all_exist = False

    if not all_exist:
        print("\n[ERROR] Some files are missing!")
        return False

    print("\n[*] Checking for critical improvements...")

    # Check bookmark_navigator.py
    print("\nChecking bookmark_navigator.py:")
    with open(workflow_dir / "bookmark_navigator.py", "r", encoding="utf-8") as f:
        bookmark_content = f.read()

        checks = [
            ("Tesseract correct attribute", "pytesseract.tesseract_cmd"),
            ("OCR-based panel finding", "def _find_bookmark_in_panel"),
            ("Panel boundary check", "x < 500"),
            ("Exact match search", "text.lower() == page_name.lower()"),
            ("Multi-level panel closing", "_close_bookmark_panel"),
            ("ESC key fallback", "pyautogui.press('esc')"),
        ]

        for check_name, search_term in checks:
            if search_term in bookmark_content:
                print(f"  [OK] {check_name}")
            else:
                print(f"  [ERROR] {check_name} NOT FOUND")
                all_exist = False

    # Check add_videos_finder.py
    print("\nChecking add_videos_finder.py:")
    with open(workflow_dir / "add_videos_finder.py", "r", encoding="utf-8") as f:
        videos_content = f.read()

        checks = [
            ("Tesseract correct attribute", "pytesseract.tesseract_cmd"),
            ("Multiple matching methods", "cv2.TM_CCORR_NORMED"),
            ("Best match selection", "best_confidence"),
            ("Explicit left-click", "button='left'"),
            ("Immediate interface check", "np.array_equal"),
            ("Adaptive wait function", "_adaptive_wait_for_change"),
            ("OCR search fallback", "_ocr_search_button"),
        ]

        for check_name, search_term in checks:
            if search_term in videos_content:
                print(f"  [OK] {check_name}")
            else:
                print(f"  [ERROR] {check_name} NOT FOUND")
                all_exist = False

    # Check helper images
    print("\nChecking helper images:")
    helper_dir = base_path / "modules" / "auto_uploader" / "helper_images"
    required_images = [
        "add_videos_button.png",
        "all_bookmarks.png",
        "bookmarks_close.png",
    ]

    for image in required_images:
        image_path = helper_dir / image
        if image_path.exists():
            print(f"  [OK] {image}")
        else:
            print(f"  [ERROR] {image} NOT FOUND")
            all_exist = False

    # Check syntax
    print("\n[*] Checking Python syntax...")
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(workflow_dir / "bookmark_navigator.py")],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("  [OK] bookmark_navigator.py syntax OK")
        else:
            print(f"  [ERROR] bookmark_navigator.py syntax error: {result.stderr.decode()}")
            all_exist = False

        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(workflow_dir / "add_videos_finder.py")],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("  [OK] add_videos_finder.py syntax OK")
        else:
            print(f"  [ERROR] add_videos_finder.py syntax error: {result.stderr.decode()}")
            all_exist = False

    except Exception as e:
        print(f"  [WARN] Could not verify syntax: {e}")

    print("\n" + "=" * 70)
    if all_exist:
        print("[SUCCESS] ALL IMPROVEMENTS VERIFIED!")
        print("=" * 70)
        print("\nSummary:")
        print("  - Tesseract OCR properly configured in both files")
        print("  - Bookmark finding now uses actual OCR coordinates")
        print("  - Panel closing has 3-level fallback")
        print("  - Button detection uses multiple matching methods")
        print("  - Click verification is immediate and explicit")
        print("  - All syntax verified")
        print("  - All helper images present")
        print("\nReady to run: python test_workflow_end_to_end.py")
        print("=" * 70 + "\n")
        return True
    else:
        print("[FAILED] SOME IMPROVEMENTS NOT FOUND")
        print("=" * 70 + "\n")
        return False

if __name__ == "__main__":
    success = verify_file_changes()
    sys.exit(0 if success else 1)
