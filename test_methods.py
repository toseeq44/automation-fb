"""
Simple test script to check if yt-dlp methods work
Run this to diagnose link grabbing issues
"""
import subprocess
import sys
from pathlib import Path

def test_simple_ytdlp():
    """Test 1: Exact command from working batch script"""
    print("\n" + "="*60)
    print("TEST 1: Simple yt-dlp command (like batch script)")
    print("="*60)

    url = "https://www.tiktok.com/@elaime.liao"
    cmd = ['yt-dlp', '--flat-playlist', '--get-url', url]

    print(f"Command: {' '.join(cmd)}")
    print("\nRunning...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        print(f"\nReturn code: {result.returncode}")
        print(f"\nSTDOUT ({len(result.stdout)} chars):")
        print(result.stdout[:1000] if result.stdout else "(empty)")

        print(f"\nSTDERR ({len(result.stderr)} chars):")
        print(result.stderr[:1000] if result.stderr else "(empty)")

        # Count URLs
        urls = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith('http')]
        print(f"\n✅ Found {len(urls)} URLs")
        if urls:
            print("First 3 URLs:")
            for url in urls[:3]:
                print(f"  - {url}")

        return len(urls) > 0

    except FileNotFoundError:
        print("❌ ERROR: yt-dlp not found! Is it installed?")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_with_cookies():
    """Test 2: With cookie file"""
    print("\n" + "="*60)
    print("TEST 2: With cookies file")
    print("="*60)

    cookie_file = Path("cookies/tiktok.txt")

    if not cookie_file.exists():
        print(f"⚠️  Cookie file not found: {cookie_file}")
        print("Skipping this test")
        return False

    print(f"✅ Cookie file exists: {cookie_file} ({cookie_file.stat().st_size} bytes)")

    url = "https://www.tiktok.com/@elaime.liao"
    cmd = ['yt-dlp', '--flat-playlist', '--get-url', '--cookies', str(cookie_file), url]

    print(f"Command: {' '.join(cmd)}")
    print("\nRunning...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        print(f"\nReturn code: {result.returncode}")

        urls = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith('http')]
        print(f"\n✅ Found {len(urls)} URLs with cookies")

        if not urls and result.stderr:
            print("\nError output:")
            print(result.stderr[:500])

        return len(urls) > 0

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_dump_json():
    """Test 3: With --dump-json to get dates"""
    print("\n" + "="*60)
    print("TEST 3: yt-dlp with --dump-json (for dates)")
    print("="*60)

    url = "https://www.tiktok.com/@elaime.liao"
    cmd = ['yt-dlp', '--dump-json', '--flat-playlist', url]

    print(f"Command: {' '.join(cmd)}")
    print("\nRunning...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        lines = [l for l in result.stdout.splitlines() if l.strip()]
        print(f"\n✅ Got {len(lines)} JSON lines")

        if lines:
            print("\nFirst line (truncated):")
            print(lines[0][:200] + "...")

        return len(lines) > 0

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    print("\n🔍 TikTok Link Grabber Diagnostic Tool")
    print("=" * 60)

    results = {}

    results['Simple'] = test_simple_ytdlp()
    results['With Cookies'] = test_with_cookies()
    results['JSON Mode'] = test_dump_json()

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")

    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)

    if not any(results.values()):
        print("""
❌ All tests failed!

Possible causes:
1. yt-dlp is not installed or not in PATH
2. TikTok is blocking your IP/region
3. TikTok changed their API and yt-dlp needs update
4. Network/firewall blocking

Solutions to try:
1. Update yt-dlp: pip install -U yt-dlp
2. Try with VPN to different region
3. Get fresh cookies using Chrome extension 'Get cookies.txt'
4. Try --cookies-from-browser chrome instead of file
        """)
    elif results['Simple'] and not results['With Cookies']:
        print("""
⚠️  Works without cookies but fails with cookies!

Problem: Cookie file might be invalid

Solutions:
1. Re-export cookies using Chrome extension 'Get cookies.txt'
2. Make sure cookies are in Netscape format
3. Ensure cookies are not expired
4. Try using --cookies-from-browser chrome instead
        """)
    elif any(results.values()):
        print("""
✅ At least one method worked!

The app should work. If it's still failing in the GUI:
1. Make sure cookie file is in the right location (cookies/tiktok.txt)
2. Check the GUI log for actual error messages
3. Try different URL formats
        """)

    print("\n")


if __name__ == '__main__':
    main()
