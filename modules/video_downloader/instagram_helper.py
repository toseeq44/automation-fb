"""
Instagram-specific helpers for cookie management and downloads.
Helps users troubleshoot Instagram authentication issues.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
import json


class InstagramCookieValidator:
    """Validates Instagram cookies and provides helpful feedback"""

    # Required cookie fields for Instagram authentication
    REQUIRED_FIELDS = [
        'sessionid',  # Primary authentication token
        'csrftoken',  # CSRF protection token
    ]

    # Optional but helpful fields
    OPTIONAL_FIELDS = [
        'ds_user_id',
        'rur',
    ]

    def __init__(self):
        self.validation_result = {
            'is_valid': False,
            'has_sessionid': False,
            'has_csrftoken': False,
            'is_expired': False,
            'file_exists': False,
            'line_count': 0,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }

    def validate_cookie_file(self, cookie_file_path: str) -> dict:
        """
        Validate Instagram cookie file and return detailed results.

        Args:
            cookie_file_path: Path to cookies.txt file (Netscape format)

        Returns:
            dict with validation results and suggestions
        """
        self.validation_result = {
            'is_valid': False,
            'has_sessionid': False,
            'has_csrftoken': False,
            'is_expired': False,
            'file_exists': False,
            'line_count': 0,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }

        cookie_path = Path(cookie_file_path)

        # Check 1: File exists
        if not cookie_path.exists():
            self.validation_result['errors'].append(f"Cookie file not found: {cookie_file_path}")
            self.validation_result['suggestions'].append(
                "📝 Create cookie file using browser extension:\n"
                "   1. Install 'Get cookies.txt LOCALLY' extension\n"
                "   2. Login to Instagram in browser\n"
                "   3. Click extension icon → Export cookies\n"
                "   4. Save as 'instagram.txt' in cookies folder"
            )
            return self.validation_result

        self.validation_result['file_exists'] = True

        # Check 2: File size
        file_size = cookie_path.stat().st_size
        if file_size < 50:  # Too small to be valid
            self.validation_result['errors'].append(f"Cookie file too small ({file_size} bytes)")
            self.validation_result['suggestions'].append(
                "⚠️ File seems empty or incomplete. Re-export cookies from browser."
            )
            return self.validation_result

        # Check 3: Parse cookies and validate content
        try:
            with open(cookie_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            self.validation_result['line_count'] = len(lines)

            sessionid_found = False
            csrftoken_found = False
            sessionid_expires = None

            for line in lines:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse Netscape cookie format
                # Format: domain flag path secure expiration name value
                parts = line.split('\t')
                if len(parts) < 7:
                    continue

                cookie_name = parts[5]
                cookie_value = parts[6]
                cookie_expires = parts[4]

                # Check for sessionid
                if cookie_name == 'sessionid':
                    sessionid_found = True
                    self.validation_result['has_sessionid'] = True

                    # Check expiration
                    try:
                        expires_timestamp = int(cookie_expires)
                        expires_date = datetime.fromtimestamp(expires_timestamp)
                        sessionid_expires = expires_date

                        if expires_date < datetime.now():
                            self.validation_result['is_expired'] = True
                            self.validation_result['errors'].append(
                                f"sessionid cookie EXPIRED on {expires_date.strftime('%Y-%m-%d %H:%M')}"
                            )
                        elif expires_date < datetime.now() + timedelta(days=1):
                            self.validation_result['warnings'].append(
                                f"⚠️ sessionid expires soon: {expires_date.strftime('%Y-%m-%d %H:%M')}"
                            )
                    except (ValueError, OverflowError):
                        pass

                    # Check if value looks valid
                    if len(cookie_value) < 20:
                        self.validation_result['warnings'].append(
                            "⚠️ sessionid value seems too short"
                        )

                # Check for csrftoken
                if cookie_name == 'csrftoken':
                    csrftoken_found = True
                    self.validation_result['has_csrftoken'] = True

                    if len(cookie_value) < 10:
                        self.validation_result['warnings'].append(
                            "⚠️ csrftoken value seems too short"
                        )

            # Final validation
            if not sessionid_found:
                self.validation_result['errors'].append(
                    "Missing 'sessionid' cookie - Instagram authentication will fail"
                )
                self.validation_result['suggestions'].append(
                    "🔑 Make sure you're LOGGED IN to Instagram when exporting cookies"
                )

            if not csrftoken_found:
                self.validation_result['warnings'].append(
                    "Missing 'csrftoken' cookie - may cause issues"
                )

            # Overall validation
            if sessionid_found and not self.validation_result['is_expired']:
                self.validation_result['is_valid'] = True

        except Exception as e:
            self.validation_result['errors'].append(f"Error parsing cookie file: {str(e)[:100]}")

        # Add suggestions based on results
        if not self.validation_result['is_valid']:
            if self.validation_result['is_expired']:
                self.validation_result['suggestions'].append(
                    "🔄 Cookies expired. Steps to fix:\n"
                    "   1. Open Instagram in browser\n"
                    "   2. Login again (or refresh page)\n"
                    "   3. Re-export cookies using extension\n"
                    "   4. Replace old instagram.txt file"
                )
            elif not self.validation_result['has_sessionid']:
                self.validation_result['suggestions'].append(
                    "⚠️ Cookie export failed. Try this:\n"
                    "   1. Close all Instagram tabs\n"
                    "   2. Open NEW tab → instagram.com\n"
                    "   3. Login with username/password\n"
                    "   4. Wait for page to fully load\n"
                    "   5. Export cookies again"
                )

        return self.validation_result

    def get_formatted_report(self, validation_result: dict = None) -> str:
        """Get human-readable validation report"""
        if validation_result is None:
            validation_result = self.validation_result

        report = []
        report.append("=" * 60)
        report.append("🔍 INSTAGRAM COOKIE VALIDATION REPORT")
        report.append("=" * 60)

        # Status
        if validation_result['is_valid']:
            report.append("✅ Status: VALID - Ready to use")
        else:
            report.append("❌ Status: INVALID - Will not work")

        report.append("")

        # Details
        report.append(f"📁 File exists: {'✅ Yes' if validation_result['file_exists'] else '❌ No'}")
        if validation_result['file_exists']:
            report.append(f"📄 Lines in file: {validation_result['line_count']}")
            report.append(f"🔑 Has sessionid: {'✅ Yes' if validation_result['has_sessionid'] else '❌ No'}")
            report.append(f"🛡️ Has csrftoken: {'✅ Yes' if validation_result['has_csrftoken'] else '⚠️ No'}")
            report.append(f"⏰ Expired: {'❌ YES' if validation_result['is_expired'] else '✅ No'}")

        report.append("")

        # Errors
        if validation_result['errors']:
            report.append("❌ ERRORS:")
            for error in validation_result['errors']:
                report.append(f"   • {error}")
            report.append("")

        # Warnings
        if validation_result['warnings']:
            report.append("⚠️ WARNINGS:")
            for warning in validation_result['warnings']:
                report.append(f"   • {warning}")
            report.append("")

        # Suggestions
        if validation_result['suggestions']:
            report.append("💡 HOW TO FIX:")
            for suggestion in validation_result['suggestions']:
                report.append(f"{suggestion}")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)


def get_instagram_cookie_instructions() -> str:
    """Get detailed instructions for setting up Instagram cookies"""

    instructions = """
╔══════════════════════════════════════════════════════════════╗
║     📸 HOW TO GET VALID INSTAGRAM COOKIES (STEP-BY-STEP)     ║
╚══════════════════════════════════════════════════════════════╝

🔧 METHOD 1: Browser Extension (RECOMMENDED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Install Chrome Extension:
   🔗 https://chrome.google.com/webstore
   Search: "Get cookies.txt LOCALLY"
   ⚠️ Make sure it says "LOCALLY" (privacy-safe)

2. Login to Instagram:
   • Open instagram.com in Chrome
   • Login with your credentials
   • Wait for feed to load completely
   • Make sure you see your profile in top right

3. Export Cookies:
   • Click extension icon (cookie symbol) in toolbar
   • Click "Export" or "Get cookies.txt"
   • Save file as: instagram.txt

4. Place Cookie File:
   📁 Save in: <project_root>/cookies/instagram.txt
   OR
   📁 Desktop/toseeq-cookies.txt (if using single mode)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 METHOD 2: Developer Tools (Manual)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Open Instagram in browser
2. Press F12 (open DevTools)
3. Go to "Application" tab
4. Left sidebar → Cookies → instagram.com
5. Find "sessionid" cookie
6. Copy the VALUE (long string)
7. Create text file manually (advanced users only)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ COMMON MISTAKES TO AVOID:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NOT logged into Instagram when exporting
❌ Using incognito/private mode (cookies won't save)
❌ Cookies exported from wrong website
❌ File saved in wrong location
❌ Using expired cookies (re-export every 24-48 hours)
❌ Account logged out after exporting cookies

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ HOW TO VERIFY COOKIES WORK:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Make sure instagram.txt file exists
2. File size should be > 1 KB
3. Open file in notepad - should have multiple lines
4. Look for line containing "sessionid"
5. Run downloader - watch for "🔑 Valid Instagram cookies" message

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 COOKIE MAINTENANCE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Re-export cookies every 1-2 days for best results
• If downloads fail, first step: re-export cookies
• Keep your Instagram account logged in browser
• Don't logout from Instagram after exporting

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return instructions


def test_instagram_cookies(cookie_file: str) -> bool:
    """Quick test if Instagram cookies are likely to work"""
    validator = InstagramCookieValidator()
    result = validator.validate_cookie_file(cookie_file)
    return result['is_valid']
