"""
Enhanced Cookie Validator for Link Grabber
Provides comprehensive validation with detailed error messages
"""

from datetime import datetime
from typing import Tuple, List, Dict, Optional
from pathlib import Path


class CookieValidationResult:
    """Detailed validation result with warnings and errors"""

    def __init__(self):
        self.is_valid = False
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.platform_tokens: Dict[str, bool] = {}
        self.expiration_info: Dict[str, str] = {}
        self.cookie_count = 0
        self.platforms_detected: List[str] = []

    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)

    def get_summary(self) -> str:
        """Get human-readable summary"""
        if not self.is_valid:
            summary = "❌ VALIDATION FAILED\n\n"
            summary += "Errors:\n"
            for i, error in enumerate(self.errors, 1):
                summary += f"  {i}. {error}\n"
        else:
            summary = "✅ COOKIES ARE VALID\n\n"
            summary += f"Total Cookies: {self.cookie_count}\n"
            summary += f"Platforms Detected: {', '.join(self.platforms_detected)}\n\n"

            if self.platform_tokens:
                summary += "Platform Authentication:\n"
                for platform, has_auth in self.platform_tokens.items():
                    status = "✅" if has_auth else "⚠️"
                    summary += f"  {status} {platform.capitalize()}: "
                    summary += "Authenticated\n" if has_auth else "No auth tokens\n"
                summary += "\n"

            if self.expiration_info:
                summary += "Expiration Status:\n"
                for platform, exp_msg in self.expiration_info.items():
                    summary += f"  {platform.capitalize()}: {exp_msg}\n"
                summary += "\n"

        if self.warnings:
            summary += "⚠️ Warnings:\n"
            for i, warning in enumerate(self.warnings, 1):
                summary += f"  {i}. {warning}\n"

        return summary

    def get_short_message(self) -> str:
        """Get short success/error message"""
        if not self.is_valid:
            return f"❌ Invalid: {self.errors[0]}"

        msg = f"✅ Valid ({self.cookie_count} cookies, {len(self.platforms_detected)} platforms)"
        if self.warnings:
            msg += f" - {len(self.warnings)} warning(s)"
        return msg


class EnhancedCookieValidator:
    """
    Comprehensive cookie validator for Link Grabber
    Validates format, expiration, platform-specific tokens
    """

    # Platform-specific required tokens
    PLATFORM_TOKENS = {
        'instagram': ['sessionid', 'csrftoken'],
        'facebook': ['c_user', 'xs'],
        'tiktok': ['sessionid'],
        'twitter': ['auth_token', 'ct0'],
        'youtube': ['SID', 'HSID'],
    }

    # Optional tokens (don't error if missing, only warn)
    OPTIONAL_TOKENS = {
        'instagram': ['rur', 'ds_user_id', 'mid'],
        'facebook': ['datr', 'sb', 'fr'],
        'tiktok': ['tt_csrf_token', 'tt_chain_token'],
        'twitter': ['guest_id'],
        'youtube': ['LOGIN_INFO', 'PREF'],
    }

    # Supported platform domains (only check these)
    SUPPORTED_DOMAINS = [
        '.instagram.com', 'instagram.com',
        '.facebook.com', 'facebook.com',
        '.tiktok.com', 'tiktok.com',
        '.twitter.com', 'twitter.com',
        '.x.com', 'x.com',
        '.youtube.com', 'youtube.com',
    ]

    # Minimum cookie counts for reasonable validation
    MIN_COOKIE_COUNT = 2

    # Cookie expiration warning threshold (days)
    EXPIRATION_WARNING_DAYS = 7

    def __init__(self):
        self.result = CookieValidationResult()

    def validate(self, cookies_text: str) -> CookieValidationResult:
        """
        Main validation method

        Args:
            cookies_text: Raw cookie text content

        Returns:
            CookieValidationResult with detailed validation info
        """
        self.result = CookieValidationResult()

        # Step 1: Basic content check
        if not self._validate_content(cookies_text):
            return self.result

        # Step 2: Format validation
        lines = cookies_text.strip().split('\n')
        if not self._validate_format(lines):
            return self.result

        # Step 3: Parse cookies
        cookies = self._parse_cookies(lines)
        if not cookies:
            self.result.add_error("No valid cookies found in the text")
            return self.result

        self.result.cookie_count = len(cookies)

        # Step 4: Detect platforms
        self._detect_platforms(cookies)

        # Step 5: Validate platform-specific tokens
        self._validate_platform_tokens(cookies)

        # Step 6: Check expiration
        self._check_expiration(cookies)

        # Step 7: Additional validations
        self._additional_validations(cookies)

        # If no errors, mark as valid
        if not self.result.errors:
            self.result.is_valid = True

        return self.result

    def _validate_content(self, cookies_text: str) -> bool:
        """Validate basic content requirements"""
        if not cookies_text:
            self.result.add_error("Cookie text is empty")
            return False

        if not cookies_text.strip():
            self.result.add_error("Cookie text contains only whitespace")
            return False

        # Check minimum length
        if len(cookies_text.strip()) < 50:
            self.result.add_error("Cookie text too short (minimum 50 characters required)")
            return False

        return True

    def _validate_format(self, lines: List[str]) -> bool:
        """Validate Netscape cookie file format"""
        # Check for Netscape header (recommended but not required)
        has_header = any('Netscape' in line for line in lines[:3])

        # Count valid cookie lines (tab-separated with 7 fields)
        valid_lines = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) >= 7:
                valid_lines += 1

        if valid_lines == 0:
            self.result.add_error(
                "No valid cookie lines found. Expected format:\n"
                ".domain.com\tTRUE\t/\tTRUE\texpiry\tname\tvalue\n\n"
                "TIP: Use 'Get cookies.txt' Chrome extension to export cookies in Netscape format"
            )
            return False

        if not has_header:
            self.result.add_warning(
                "Netscape header missing (# Netscape HTTP Cookie File). "
                "This is recommended but not required."
            )

        # Note: We don't check MIN_COOKIE_COUNT here because we filter to
        # only relevant platform cookies later. The actual count will be checked
        # after parsing and filtering.

        return True

    def _parse_cookies(self, lines: List[str]) -> List[Dict[str, str]]:
        """
        Parse cookie lines into structured format.
        Only returns cookies from SUPPORTED platforms to avoid checking irrelevant cookies.
        """
        cookies = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) < 7:
                continue

            try:
                domain = parts[0]

                # FILTER: Only include cookies from supported platforms
                # This prevents checking Gmail, Perplexity, and other irrelevant cookies
                is_relevant = any(
                    supported_domain in domain.lower()
                    for supported_domain in self.SUPPORTED_DOMAINS
                )

                if not is_relevant:
                    continue  # Skip irrelevant cookies

                cookie = {
                    'domain': domain,
                    'flag': parts[1],
                    'path': parts[2],
                    'secure': parts[3],
                    'expiry': parts[4],
                    'name': parts[5],
                    'value': parts[6],
                    'line_number': line_num
                }
                cookies.append(cookie)
            except Exception as e:
                self.result.add_warning(f"Failed to parse line {line_num}: {str(e)}")
                continue

        return cookies

    def _detect_platforms(self, cookies: List[Dict[str, str]]):
        """Detect which platforms are present in cookies"""
        platform_domains = {
            'instagram': ['.instagram.com', 'instagram.com'],
            'facebook': ['.facebook.com', 'facebook.com'],
            'tiktok': ['.tiktok.com', 'tiktok.com'],
            'twitter': ['.twitter.com', 'twitter.com', '.x.com', 'x.com'],
            'youtube': ['.youtube.com', 'youtube.com'],
        }

        detected = set()

        for cookie in cookies:
            domain = cookie['domain'].lower()
            for platform, domains in platform_domains.items():
                if any(d in domain for d in domains):
                    detected.add(platform)

        self.result.platforms_detected = sorted(list(detected))

        if not self.result.platforms_detected:
            self.result.add_warning(
                "No known platforms detected (Instagram, Facebook, TikTok, Twitter, YouTube). "
                "Cookies may still work for other platforms."
            )

    def _validate_platform_tokens(self, cookies: List[Dict[str, str]]):
        """Validate platform-specific authentication tokens"""
        # Create cookie name index by platform
        platform_cookies = {}

        for cookie in cookies:
            domain = cookie['domain'].lower()
            cookie_name = cookie['name']

            # Map to platform
            if 'instagram' in domain:
                platform_cookies.setdefault('instagram', []).append(cookie_name)
            elif 'facebook' in domain:
                platform_cookies.setdefault('facebook', []).append(cookie_name)
            elif 'tiktok' in domain:
                platform_cookies.setdefault('tiktok', []).append(cookie_name)
            elif 'twitter' in domain or 'x.com' in domain:
                platform_cookies.setdefault('twitter', []).append(cookie_name)
            elif 'youtube' in domain:
                platform_cookies.setdefault('youtube', []).append(cookie_name)

        # Check required tokens for each detected platform
        for platform in self.result.platforms_detected:
            if platform not in self.PLATFORM_TOKENS:
                continue

            required_tokens = self.PLATFORM_TOKENS[platform]
            actual_tokens = platform_cookies.get(platform, [])

            has_all_tokens = all(
                any(token in cookie_name for cookie_name in actual_tokens)
                for token in required_tokens
            )

            self.result.platform_tokens[platform] = has_all_tokens

            if not has_all_tokens:
                missing = [
                    token for token in required_tokens
                    if not any(token in c for c in actual_tokens)
                ]
                self.result.add_warning(
                    f"{platform.capitalize()}: Missing authentication tokens: {', '.join(missing)}. "
                    f"This may cause authentication failures."
                )

    def _check_expiration(self, cookies: List[Dict[str, str]]):
        """
        Check cookie expiration dates.
        Only checks REQUIRED cookies for authentication.
        Handles session cookies (expiry=0) properly.
        """
        now = datetime.now()

        # Track expiration by platform
        platform_expiration = {}

        # Deduplicate cookies to avoid multiple errors for same cookie
        seen_cookies = set()

        for cookie in cookies:
            try:
                # Determine platform first
                domain = cookie['domain'].lower()
                platform = 'unknown'
                if 'instagram' in domain:
                    platform = 'instagram'
                elif 'facebook' in domain:
                    platform = 'facebook'
                elif 'tiktok' in domain:
                    platform = 'tiktok'
                elif 'twitter' in domain or 'x.com' in domain:
                    platform = 'twitter'
                elif 'youtube' in domain:
                    platform = 'youtube'

                # Deduplicate: skip if we've seen this cookie before
                cookie_key = f"{platform}_{cookie['name']}"
                if cookie_key in seen_cookies:
                    continue
                seen_cookies.add(cookie_key)

                # Only check expiration for REQUIRED authentication cookies
                # Skip optional cookies (like rur, datr, etc.)
                cookie_name = cookie['name']
                is_required = False

                if platform in self.PLATFORM_TOKENS:
                    required_tokens = self.PLATFORM_TOKENS[platform]
                    is_required = any(token in cookie_name for token in required_tokens)

                # If not a required cookie, skip expiration check
                if not is_required:
                    continue

                # Parse expiration
                expiry_timestamp = int(cookie['expiry'])

                # FIX: Session cookies (expiry=0) are VALID until browser closes
                if expiry_timestamp == 0:
                    # Session cookie - valid
                    if platform not in platform_expiration:
                        platform_expiration[platform] = "✅ Session cookie (valid)"
                    continue

                # Regular cookie with expiration date
                expiry_date = datetime.fromtimestamp(expiry_timestamp)

                # Check if expired
                if expiry_date < now:
                    self.result.add_error(
                        f"{platform.capitalize()} cookie '{cookie['name']}' has EXPIRED "
                        f"(expired on {expiry_date.strftime('%Y-%m-%d')})"
                    )
                    platform_expiration[platform] = "❌ Expired"
                else:
                    days_until_expiry = (expiry_date - now).days

                    # Store earliest expiration for platform
                    if platform not in platform_expiration or "days" in platform_expiration.get(platform, ""):
                        if days_until_expiry <= self.EXPIRATION_WARNING_DAYS:
                            platform_expiration[platform] = f"⚠️ Expires in {days_until_expiry} days"
                            self.result.add_warning(
                                f"{platform.capitalize()}: Cookie '{cookie['name']}' expires in {days_until_expiry} days"
                            )
                        else:
                            if platform not in platform_expiration:
                                platform_expiration[platform] = f"✅ Valid for {days_until_expiry} days"

            except (ValueError, TypeError):
                # Only warn if it's a required cookie
                if is_required:
                    self.result.add_warning(
                        f"Invalid expiration date for cookie '{cookie['name']}' (line {cookie['line_number']})"
                    )

        self.result.expiration_info = platform_expiration

    def _additional_validations(self, cookies: List[Dict[str, str]]):
        """Additional validation checks - only for required authentication cookies"""

        # Only check length for REQUIRED authentication cookies
        for cookie in cookies:
            domain = cookie['domain'].lower()
            cookie_name = cookie['name']
            cookie_value = cookie['value']

            # Instagram validation
            if 'instagram' in domain:
                if cookie_name == 'sessionid':
                    # Check if empty
                    if not cookie_value.strip():
                        self.result.add_error("Instagram sessionid is empty")
                    # Check length (only if not empty)
                    elif len(cookie_value) < 20:
                        self.result.add_error(
                            f"Instagram sessionid is too short ({len(cookie_value)} chars). "
                            f"Valid sessionid should be at least 20 characters."
                        )
                elif cookie_name == 'csrftoken':
                    # Check if empty
                    if not cookie_value.strip():
                        self.result.add_error("Instagram csrftoken is empty")
                    # Check length (only if not empty)
                    elif len(cookie_value) < 10:
                        self.result.add_error(
                            f"Instagram csrftoken is too short ({len(cookie_value)} chars). "
                            f"Valid csrftoken should be at least 10 characters."
                        )

            # Facebook validation
            elif 'facebook' in domain:
                if cookie_name == 'c_user':
                    if not cookie_value.strip():
                        self.result.add_error("Facebook c_user is empty")
                elif cookie_name == 'xs':
                    if not cookie_value.strip():
                        self.result.add_error("Facebook xs is empty")

            # TikTok validation
            elif 'tiktok' in domain:
                if cookie_name == 'sessionid':
                    if not cookie_value.strip():
                        self.result.add_error("TikTok sessionid is empty")


def validate_cookie_file(file_path: Path) -> CookieValidationResult:
    """
    Validate a cookie file

    Args:
        file_path: Path to cookie file

    Returns:
        CookieValidationResult with validation details
    """
    validator = EnhancedCookieValidator()

    try:
        if not file_path.exists():
            result = CookieValidationResult()
            result.add_error(f"Cookie file not found: {file_path}")
            return result

        if file_path.stat().st_size == 0:
            result = CookieValidationResult()
            result.add_error("Cookie file is empty")
            return result

        with open(file_path, 'r', encoding='utf-8') as f:
            cookies_text = f.read()

        return validator.validate(cookies_text)

    except Exception as e:
        result = CookieValidationResult()
        result.add_error(f"Error reading cookie file: {str(e)}")
        return result
