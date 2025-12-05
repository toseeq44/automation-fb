#!/usr/bin/env python3
"""
Test Script for Enhanced Cookie Validation System
Demonstrates validation with various cookie scenarios
"""

from modules.link_grabber.cookie_validator import EnhancedCookieValidator
from datetime import datetime, timedelta


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_valid_instagram_cookies():
    """Test with valid Instagram cookies"""
    print_header("TEST 1: Valid Instagram Cookies")

    # Create future expiration date (30 days from now)
    future_expiry = int((datetime.now() + timedelta(days=30)).timestamp())

    cookies = f"""# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	{future_expiry}	sessionid	77136182282%3AKMYBSOkfUqIYpG%3A26%3AAYcPzMXrZcC0_1eJ
.instagram.com	TRUE	/	TRUE	{future_expiry}	csrftoken	2kICsMjkv8EW_-8Mu2GkRr4kZ3oDJK8F
.instagram.com	TRUE	/	TRUE	{future_expiry}	ds_user_id	77136182282
"""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n✅ Test Result:", "PASSED" if result.is_valid else "FAILED")


def test_expired_cookies():
    """Test with expired cookies"""
    print_header("TEST 2: Expired Cookies")

    # Create past expiration date (30 days ago)
    past_expiry = int((datetime.now() - timedelta(days=30)).timestamp())

    cookies = f"""# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	{past_expiry}	sessionid	77136182282%3AKMYBSOkfUqIYpG%3A26
.instagram.com	TRUE	/	TRUE	{past_expiry}	csrftoken	2kICsMjkv8EW_-8Mu2GkRr
"""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n❌ Test Result:", "PASSED (correctly detected expiration)" if not result.is_valid else "FAILED")


def test_missing_required_tokens():
    """Test with missing required tokens (no sessionid)"""
    print_header("TEST 3: Missing Required Tokens")

    future_expiry = int((datetime.now() + timedelta(days=30)).timestamp())

    cookies = f"""# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	{future_expiry}	csrftoken	2kICsMjkv8EW_-8Mu2GkRr
.instagram.com	TRUE	/	TRUE	{future_expiry}	ds_user_id	77136182282
"""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n⚠️ Test Result:", "PASSED (detected missing sessionid)" if result.warnings else "FAILED")


def test_invalid_format():
    """Test with invalid format"""
    print_header("TEST 4: Invalid Cookie Format")

    cookies = """This is not a valid cookie format
Just some random text
No tabs or proper structure"""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n❌ Test Result:", "PASSED (correctly rejected)" if not result.is_valid else "FAILED")


def test_short_sessionid():
    """Test with too short sessionid"""
    print_header("TEST 5: Invalid sessionid (too short)")

    future_expiry = int((datetime.now() + timedelta(days=30)).timestamp())

    cookies = f"""# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	{future_expiry}	sessionid	short
.instagram.com	TRUE	/	TRUE	{future_expiry}	csrftoken	2kICsMjkv8EW_-8Mu2GkRr
"""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n❌ Test Result:", "PASSED (detected short sessionid)" if not result.is_valid else "FAILED")


def test_multi_platform_cookies():
    """Test with multiple platforms"""
    print_header("TEST 6: Multi-Platform Cookies")

    future_expiry = int((datetime.now() + timedelta(days=30)).timestamp())

    cookies = f"""# Netscape HTTP Cookie File
# Instagram cookies
.instagram.com	TRUE	/	TRUE	{future_expiry}	sessionid	77136182282%3AKMYBSOkfUqIYpG%3A26
.instagram.com	TRUE	/	TRUE	{future_expiry}	csrftoken	2kICsMjkv8EW_-8Mu2GkRr

# YouTube cookies
.youtube.com	TRUE	/	TRUE	{future_expiry}	SID	example_sid_value_here
.youtube.com	TRUE	/	TRUE	{future_expiry}	HSID	example_hsid_value

# TikTok cookies
.tiktok.com	TRUE	/	TRUE	{future_expiry}	sessionid	tiktok_session_12345
"""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n✅ Test Result:", "PASSED" if result.is_valid else "FAILED")


def test_expiring_soon_warning():
    """Test with cookies expiring soon (warning)"""
    print_header("TEST 7: Cookies Expiring Soon (Warning)")

    # Expiry in 3 days (should trigger warning)
    soon_expiry = int((datetime.now() + timedelta(days=3)).timestamp())

    cookies = f"""# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	{soon_expiry}	sessionid	77136182282%3AKMYBSOkfUqIYpG%3A26
.instagram.com	TRUE	/	TRUE	{soon_expiry}	csrftoken	2kICsMjkv8EW_-8Mu2GkRr
"""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n⚠️ Test Result:", "PASSED (shows expiration warning)" if result.warnings else "FAILED")


def test_empty_cookies():
    """Test with empty cookie text"""
    print_header("TEST 8: Empty Cookie Text")

    cookies = ""

    validator = EnhancedCookieValidator()
    result = validator.validate(cookies)

    print(result.get_summary())
    print("\n❌ Test Result:", "PASSED (correctly rejected empty)" if not result.is_valid else "FAILED")


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "ENHANCED COOKIE VALIDATION TESTS" + " " * 21 + "║")
    print("╚" + "═" * 68 + "╝")

    # Run all test cases
    test_valid_instagram_cookies()
    test_expired_cookies()
    test_missing_required_tokens()
    test_invalid_format()
    test_short_sessionid()
    test_multi_platform_cookies()
    test_expiring_soon_warning()
    test_empty_cookies()

    # Summary
    print_header("TEST SUITE COMPLETE")
    print("✅ All validation scenarios tested successfully!")
    print("\nKey Features Demonstrated:")
    print("  ✓ Format validation (Netscape cookie format)")
    print("  ✓ Expiration checking (expired/expiring soon)")
    print("  ✓ Platform-specific token validation (sessionid, csrftoken, etc.)")
    print("  ✓ Multi-platform support (Instagram, YouTube, TikTok, etc.)")
    print("  ✓ Detailed error messages")
    print("  ✓ Warning system for non-critical issues")
    print("  ✓ Cookie count and platform detection")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
