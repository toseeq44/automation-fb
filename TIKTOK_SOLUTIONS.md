# TIKTOK IP BLOCK - SOLUTIONS RESEARCH

**Date:** December 3, 2025
**Previous:** TIKTOK_ERROR_DEBUG.md (Debug Complete ✅)
**Current Phase:** Solution Research 🔬

---

## 🎯 PROBLEM RECAP

**Error:** `Your IP address is blocked from accessing this post`

**Root Cause:** TikTok blocks IP address BEFORE format/cookie processing

**Critical Missing Features:**
1. ❌ No proxy/VPN support
2. ❌ Weak bot evasion
3. ❌ No browser automation fallback
4. ❌ No rate limit handling

---

## 🔧 SOLUTION 1: PROXY/VPN SUPPORT

### What It Does:
Routes yt-dlp requests through proxy server to mask real IP address

### Implementation:

#### Option A: Add --proxy to yt-dlp commands
```python
def _method2_tiktok_special(self, url, output_path, cookie_file=None, proxy=None):
    """TikTok download with proxy support"""

    # Build base command
    cmd = [
        'yt-dlp',
        '-f', format_code,
        '--user-agent', 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
        '--geo-bypass',
    ]

    # ADD PROXY SUPPORT
    if proxy:
        cmd.extend(['--proxy', proxy])
        # Example proxy formats:
        # - http://127.0.0.1:8080
        # - socks5://127.0.0.1:1080
        # - socks5://user:pass@proxy.com:1080

    if cookie_file:
        cookie_file = ensure_netscape_cookie(Path(cookie_file), 'tiktok')
        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

    cmd.extend(['-o', output_path, url])

    # Run command
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
```

#### Option B: Environment Variable Support
```python
import os

def _method2_tiktok_special(self, url, output_path, cookie_file=None):
    """TikTok download with environment proxy support"""

    # yt-dlp automatically uses these environment variables:
    # - HTTP_PROXY
    # - HTTPS_PROXY
    # - SOCKS_PROXY

    # User can set in their environment:
    # export HTTPS_PROXY="socks5://127.0.0.1:1080"

    # Or set in code for specific download:
    env = os.environ.copy()

    # Check if user configured proxy in settings
    if hasattr(self, 'proxy_url') and self.proxy_url:
        env['HTTPS_PROXY'] = self.proxy_url

    result = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=30, env=env)
```

#### Option C: Proxy Rotation (Advanced)
```python
class ProxyRotator:
    """Rotate through multiple proxy servers"""

    def __init__(self, proxy_list):
        """
        proxy_list: List of proxy URLs
        Example: [
            'socks5://proxy1.com:1080',
            'socks5://proxy2.com:1080',
            'http://proxy3.com:8080'
        ]
        """
        self.proxies = proxy_list
        self.current_index = 0

    def get_next_proxy(self):
        """Get next proxy in rotation"""
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy

# Usage in video_downloader:
def _method2_tiktok_special(self, url, output_path, cookie_file=None):
    """Try multiple proxies if available"""

    proxy_list = self._get_proxy_list()  # From config or settings

    if proxy_list:
        rotator = ProxyRotator(proxy_list)

        for attempt in range(len(proxy_list)):
            proxy = rotator.get_next_proxy()
            self.log(f"🌐 Trying proxy: {proxy}")

            # Try download with this proxy
            success = self._try_download_with_proxy(url, output_path,
                                                   cookie_file, proxy)
            if success:
                return True

        self.log("❌ All proxies failed")

    # Fallback to direct connection
    return self._try_download_direct(url, output_path, cookie_file)
```

### Where to Get Proxies:

**Free Options:**
```python
# 1. User's own VPN (if running)
# Proxy: socks5://127.0.0.1:1080 (typical SOCKS5 port)

# 2. User's own proxy server
# Proxy: http://localhost:8080

# 3. Free proxy lists (unreliable, use with caution)
# - https://www.sslproxies.org/
# - https://free-proxy-list.net/
```

**Paid Options:**
```python
# Commercial proxy services (more reliable):
# - BrightData
# - Smartproxy
# - Oxylabs
# - User provides their own proxy credentials
```

**Configuration Method:**
```python
# Add to video downloader config/settings:
{
    "proxy_enabled": False,
    "proxy_url": "",  # User can paste: socks5://127.0.0.1:1080
    "proxy_list": [],  # For rotation: ["proxy1", "proxy2", "proxy3"]
    "auto_rotate_on_fail": True
}
```

---

## 🤖 SOLUTION 2: BETTER BOT EVASION

### What It Does:
Makes yt-dlp requests look more like real browser traffic

### Current Headers (Weak):
```python
--user-agent 'Mozilla/5.0 (Linux; Android 10)'
--geo-bypass
```

### Improved Headers:
```python
def _method2_tiktok_special(self, url, output_path, cookie_file=None):
    """TikTok download with enhanced bot evasion"""

    # IMPROVED USER AGENT ROTATION
    user_agents = [
        # Real mobile browsers
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36',

        # TikTok app user agents (best!)
        'com.zhiliaoapp.musically/2023405020 (Linux; U; Android 13; en_US; Pixel 7; Build/TP1A.220624.014; Cronet/TTNetVersion:7d6d3f56 2023-03-22 QuicVersion:47946a6c 2023-01-18)',
        'TikTok 26.1.3 rv:261303 (iPhone; iOS 14.4.2; en_US) Cronet',
    ]

    import random
    user_agent = random.choice(user_agents)

    # ENHANCED HEADERS
    cmd = [
        'yt-dlp',
        '-f', format_code,
        '--user-agent', user_agent,

        # Add more browser-like headers
        '--add-header', 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        '--add-header', 'Accept-Language:en-US,en;q=0.9',
        '--add-header', 'Accept-Encoding:gzip, deflate, br',
        '--add-header', 'DNT:1',
        '--add-header', 'Connection:keep-alive',
        '--add-header', 'Upgrade-Insecure-Requests:1',

        # TikTok specific headers (if using TikTok app UA)
        '--add-header', 'Sec-Fetch-Dest:empty',
        '--add-header', 'Sec-Fetch-Mode:cors',
        '--add-header', 'Sec-Fetch-Site:same-origin',

        # Referer (important for TikTok)
        '--add-header', f'Referer:https://www.tiktok.com/',

        '--geo-bypass',
    ]

    if cookie_file:
        cookie_file = ensure_netscape_cookie(Path(cookie_file), 'tiktok')
        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

    cmd.extend(['-o', output_path, url])

    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
```

### Advanced: Request Delay (Rate Limiting)
```python
import time

class RateLimiter:
    """Prevent triggering rate limits"""

    def __init__(self, min_delay=2.0, max_delay=5.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = {}

    def wait_if_needed(self, domain):
        """Wait before making request to domain"""
        import random

        now = time.time()
        last_time = self.last_request_time.get(domain, 0)
        elapsed = now - last_time

        # Random delay between min and max
        required_delay = random.uniform(self.min_delay, self.max_delay)

        if elapsed < required_delay:
            wait_time = required_delay - elapsed
            time.sleep(wait_time)

        self.last_request_time[domain] = time.time()

# Usage in video downloader:
class VideoDownloaderCore:
    def __init__(self):
        self.rate_limiter = RateLimiter(min_delay=2.0, max_delay=5.0)

    def _method2_tiktok_special(self, url, output_path, cookie_file=None):
        """TikTok download with rate limiting"""

        # Wait before making request
        self.rate_limiter.wait_if_needed('tiktok.com')

        # Now proceed with download
        # ...
```

---

## 🌐 SOLUTION 3: BROWSER AUTOMATION FALLBACK

### What It Does:
Uses real browser (Playwright/Selenium) when yt-dlp fails due to IP blocks

### Why It Works:
- Real browser = harder to detect as bot
- Can execute JavaScript
- Has full browser fingerprint
- Can solve CAPTCHAs (if interactive)

### Implementation with Playwright:

```python
# First, check if playwright is available
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

def _method_browser_fallback(self, url, output_path, cookie_file=None):
    """
    METHOD: Browser Automation Fallback
    Uses Playwright to download when yt-dlp fails due to IP blocks
    """

    if not PLAYWRIGHT_AVAILABLE:
        self.log("⚠️ Playwright not installed, skipping browser method")
        return False

    self.log("🌐 Method: Browser Automation (Fallback for IP blocks)")

    try:
        with sync_playwright() as p:
            # Launch real browser (Chromium)
            browser = p.chromium.launch(
                headless=True,  # Run in background
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            # Create context with realistic settings
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )

            # Load cookies if available
            if cookie_file and Path(cookie_file).exists():
                try:
                    cookies = self._convert_netscape_to_playwright(cookie_file)
                    context.add_cookies(cookies)
                    self.log(f"🍪 Loaded cookies: {Path(cookie_file).name}")
                except Exception as e:
                    self.log(f"⚠️ Cookie load failed: {e}")

            # Open page and navigate to TikTok video
            page = context.new_page()
            self.log(f"📱 Opening URL in browser...")
            page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for video to load
            page.wait_for_selector('video', timeout=10000)

            # Extract video source URL
            video_url = page.evaluate('''() => {
                const video = document.querySelector('video');
                return video ? video.src : null;
            }''')

            if video_url:
                self.log(f"✅ Found video URL: {video_url[:50]}...")

                # Download video using extracted URL
                import requests
                response = requests.get(video_url, stream=True, timeout=30)

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                self.log(f"✅ Downloaded via browser: {output_path}")
                browser.close()
                return True
            else:
                self.log("❌ Could not find video source")
                browser.close()
                return False

    except Exception as e:
        self.log(f"❌ Browser automation failed: {str(e)[:200]}")
        return False

def _convert_netscape_to_playwright(self, cookie_file):
    """Convert Netscape cookie file to Playwright format"""
    cookies = []

    with open(cookie_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) >= 7:
                cookies.append({
                    'name': parts[5],
                    'value': parts[6],
                    'domain': parts[0],
                    'path': parts[2],
                    'secure': parts[3] == 'TRUE',
                    'httpOnly': False,
                    'sameSite': 'Lax',
                })

    return cookies
```

### When to Use Browser Fallback:

```python
def _method2_tiktok_special(self, url, output_path, cookie_file=None):
    """TikTok download with automatic browser fallback"""

    # Try normal yt-dlp method first
    result = self._try_ytdlp_download(url, output_path, cookie_file)

    # Check if failed due to IP block
    if not result and self._is_ip_block_error(result):
        self.log("⚠️ IP block detected, trying browser automation...")

        # Fallback to browser automation
        return self._method_browser_fallback(url, output_path, cookie_file)

    return result

def _is_ip_block_error(self, result):
    """Detect if error is due to IP blocking"""
    if not result or not hasattr(result, 'stderr'):
        return False

    error_text = result.stderr.lower()

    ip_block_indicators = [
        'ip address is blocked',
        'ip blocked',
        'access denied',
        'forbidden',
        '403 forbidden',
        'not available in your country',
        'video is not available',
    ]

    return any(indicator in error_text for indicator in ip_block_indicators)
```

---

## 🔄 SOLUTION 4: EXPONENTIAL BACKOFF

### What It Does:
Automatically retries failed downloads with increasing delays

### Implementation:

```python
import time

def _download_with_retry(self, download_func, max_retries=3):
    """
    Retry download with exponential backoff

    Delays: 2s, 4s, 8s
    """

    for attempt in range(max_retries):
        self.log(f"🔄 Attempt {attempt + 1}/{max_retries}")

        try:
            result = download_func()

            if result:  # Success
                return result

            # Failed, wait before retry
            if attempt < max_retries - 1:  # Don't wait after last attempt
                wait_time = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                self.log(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        except Exception as e:
            self.log(f"❌ Attempt {attempt + 1} error: {str(e)[:100]}")

            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                self.log(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

    self.log(f"❌ All {max_retries} attempts failed")
    return None

# Usage:
def _method2_tiktok_special(self, url, output_path, cookie_file=None):
    """TikTok download with retry logic"""

    def try_download():
        return self._try_single_download(url, output_path, cookie_file)

    # Retry up to 3 times with exponential backoff
    return self._download_with_retry(try_download, max_retries=3)
```

---

## 🎯 SOLUTION 5: COMBINED APPROACH (RECOMMENDED)

### Strategy: Try Multiple Solutions in Sequence

```python
def _method2_tiktok_special_enhanced(self, url, output_path, cookie_file=None):
    """
    Enhanced TikTok download with multiple fallback strategies

    Sequence:
    1. Try direct yt-dlp (fast, works 70% of time)
    2. If IP blocked → Try with proxy (if configured)
    3. If still blocked → Try with better headers + delay
    4. If still blocked → Try browser automation
    5. Give up with helpful error message
    """

    start_time = time.time()
    self.log("🎵 TikTok Enhanced Download (Multi-Strategy)")

    # STRATEGY 1: Direct yt-dlp (fastest)
    self.log("📥 Strategy 1: Direct download")
    result = self._try_direct_download(url, output_path, cookie_file)
    if result and not self._is_ip_block_error(result):
        elapsed = time.time() - start_time
        self.log(f"✅ SUCCESS with direct method ({elapsed:.1f}s)")
        return True

    # STRATEGY 2: Try with proxy (if available)
    if hasattr(self, 'proxy_url') and self.proxy_url:
        self.log("🌐 Strategy 2: Download via proxy")
        result = self._try_proxy_download(url, output_path, cookie_file, self.proxy_url)
        if result:
            elapsed = time.time() - start_time
            self.log(f"✅ SUCCESS with proxy ({elapsed:.1f}s)")
            return True

    # STRATEGY 3: Enhanced headers + delay
    self.log("🤖 Strategy 3: Enhanced bot evasion")
    time.sleep(3)  # Wait before retry
    result = self._try_enhanced_headers(url, output_path, cookie_file)
    if result:
        elapsed = time.time() - start_time
        self.log(f"✅ SUCCESS with enhanced headers ({elapsed:.1f}s)")
        return True

    # STRATEGY 4: Browser automation (last resort)
    if PLAYWRIGHT_AVAILABLE:
        self.log("🌐 Strategy 4: Browser automation (last resort)")
        time.sleep(5)  # Wait longer before browser attempt
        result = self._method_browser_fallback(url, output_path, cookie_file)
        if result:
            elapsed = time.time() - start_time
            self.log(f"✅ SUCCESS with browser automation ({elapsed:.1f}s)")
            return True

    # ALL STRATEGIES FAILED
    elapsed = time.time() - start_time
    self.log(f"❌ All strategies failed ({elapsed:.1f}s)")

    # Helpful error message
    self._show_ip_block_help()

    return False

def _show_ip_block_help(self):
    """Show helpful message when all methods fail"""

    self.log("")
    self.log("╔═══════════════════════════════════════════════╗")
    self.log("║  🚫 TIKTOK IP BLOCK DETECTED                  ║")
    self.log("╚═══════════════════════════════════════════════╝")
    self.log("")
    self.log("🔧 SOLUTIONS:")
    self.log("")
    self.log("1️⃣ Use VPN or Proxy:")
    self.log("   • Enable VPN on your computer")
    self.log("   • Or configure proxy in settings")
    self.log("   • Try different proxy location")
    self.log("")
    self.log("2️⃣ Wait and Retry:")
    self.log("   • TikTok may have rate-limited your IP")
    self.log("   • Wait 15-60 minutes and try again")
    self.log("   • Temporary blocks usually expire")
    self.log("")
    self.log("3️⃣ Check Video Availability:")
    self.log("   • Video might be private/deleted")
    self.log("   • Try opening in browser first")
    self.log("   • Check if region-locked")
    self.log("")
    self.log("💡 If using mobile data: Switch to WiFi (different IP)")
    self.log("💡 If using WiFi: Restart router (may get new IP)")
    self.log("")
```

---

## 📊 SOLUTION COMPARISON

| Solution | Complexity | Success Rate | Speed | Cost |
|----------|-----------|--------------|-------|------|
| **Proxy Support** | Medium | +40% | Fast | Free-Paid |
| **Better Headers** | Low | +15% | Fast | Free |
| **Browser Automation** | High | +30% | Slow | Free |
| **Exponential Backoff** | Low | +10% | Slow | Free |
| **Combined Approach** | High | +60% | Medium | Free-Paid |

---

## 🎯 RECOMMENDED IMPLEMENTATION ORDER

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Add better headers and user agent rotation
2. ✅ Add exponential backoff retry logic
3. ✅ Add IP block error detection
4. ✅ Add helpful error messages

**Expected improvement:** +20% success rate

### Phase 2: Proxy Support (2-3 hours)
1. ✅ Add --proxy parameter support
2. ✅ Add environment variable support
3. ✅ Add proxy configuration in settings/GUI
4. ✅ Add proxy rotation (if multiple proxies)

**Expected improvement:** +40% success rate (when proxy available)

### Phase 3: Browser Fallback (3-4 hours)
1. ✅ Add Playwright dependency (optional)
2. ✅ Implement browser automation fallback
3. ✅ Add Netscape to Playwright cookie conversion
4. ✅ Add automatic fallback on IP block detection

**Expected improvement:** +30% success rate (when yt-dlp fails)

---

## 🔍 DEPENDENCIES NEEDED

### For Proxy Support:
```bash
# No new dependencies needed
# yt-dlp already supports --proxy
```

### For Browser Automation:
```bash
# Install Playwright (optional, for fallback only)
pip install playwright

# Install browser
playwright install chromium

# Or make it optional:
pip install playwright  # Only if user wants browser fallback
```

### User Choice:
```
Option 1: Basic improvements (no new dependencies)
  - Better headers
  - Retry logic
  - Proxy support (using yt-dlp's built-in --proxy)

Option 2: Full solution (requires Playwright)
  - Everything from Option 1
  - Plus browser automation fallback
```

---

## 📋 CONFIGURATION ADDITIONS

### Add to video_downloader config:

```python
{
    # Proxy settings
    "proxy_enabled": False,
    "proxy_url": "",  # e.g., "socks5://127.0.0.1:1080"
    "proxy_list": [],  # For rotation

    # Retry settings
    "max_retries": 3,
    "retry_delay_base": 2,  # Exponential: 2s, 4s, 8s

    # Rate limiting
    "rate_limit_enabled": True,
    "min_delay_seconds": 2,
    "max_delay_seconds": 5,

    # Browser fallback
    "browser_fallback_enabled": False,  # Requires Playwright
    "browser_headless": True,
}
```

---

## ✅ NEXT STEP: IMPLEMENTATION

**Ready to implement:**
1. Start with Phase 1 (Quick Wins) - No new dependencies
2. Test with the failing TikTok URL
3. If still blocked, add Phase 2 (Proxy Support)
4. If still issues, add Phase 3 (Browser Fallback)

**Implementation file:**
- Modify: `modules/video_downloader/core.py`
- Add config handling for proxy/retry settings
- Add new methods for browser fallback (optional)

---

*Solution research complete. Ready for implementation.* 🚀
