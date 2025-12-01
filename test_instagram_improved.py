"""
TEST SCRIPT FOR IMPROVED INSTAGRAM LINK GRABBER
Quick testing ke liye
"""

from instagram_linkgrabber_improved import InstagramLinkGrabber
import time

def test_single_account():
    """Test single Instagram account"""
    print("=" * 70)
    print("🧪 TESTING SINGLE ACCOUNT")
    print("=" * 70)

    grabber = InstagramLinkGrabber(
        cookie_file='cookies/instagram.txt'
    )

    # Test URL
    url = "https://www.instagram.com/anvil.anna"

    print(f"\n📥 Extracting links from: {url}")
    start_time = time.time()

    links = grabber.extract_links(url, max_posts=50)  # Limit to 50 for testing

    elapsed = time.time() - start_time

    if links:
        print(f"\n✅ SUCCESS!")
        print(f"📊 Extracted: {len(links)} links")
        print(f"⏱️ Time taken: {elapsed:.2f} seconds")

        # Save to file
        grabber.save_to_file(links, 'test_output/anvil.anna_test.txt', 'anvil.anna')

        # Show first 5 links
        print(f"\n📋 First 5 links:")
        for i, link in enumerate(links[:5], 1):
            title = link.get('title', 'No title')[:50]
            date = link.get('date', '00000000')
            if date != '00000000':
                date_str = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
            else:
                date_str = "Unknown"
            print(f"{i}. {link['url']}")
            print(f"   Date: {date_str} | Title: {title}")
    else:
        print(f"\n❌ FAILED - No links extracted")

def test_multiple_accounts():
    """Test multiple Instagram accounts"""
    print("\n" + "=" * 70)
    print("🧪 TESTING MULTIPLE ACCOUNTS")
    print("=" * 70)

    grabber = InstagramLinkGrabber(
        cookie_file='cookies/instagram.txt'
    )

    # Test accounts
    accounts = [
        'anvil.anna',
        'massageclipp',
        # Add more accounts to test
    ]

    results = {}

    for username in accounts:
        print(f"\n📥 Processing @{username}...")
        url = f"https://www.instagram.com/{username}"

        start_time = time.time()
        links = grabber.extract_links(url, max_posts=20)  # Limit to 20 for quick test
        elapsed = time.time() - start_time

        results[username] = {
            'success': len(links) > 0,
            'count': len(links),
            'time': elapsed
        }

        if links:
            print(f"   ✅ Success: {len(links)} links in {elapsed:.2f}s")
            grabber.save_to_file(links, f'test_output/{username}_test.txt', username)
        else:
            print(f"   ❌ Failed")

    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)

    total_success = sum(1 for r in results.values() if r['success'])
    total_links = sum(r['count'] for r in results.values())

    print(f"\n✅ Success: {total_success}/{len(accounts)} accounts")
    print(f"📊 Total links: {total_links}")

    for username, result in results.items():
        status = "✅" if result['success'] else "❌"
        print(f"{status} @{username}: {result['count']} links ({result['time']:.2f}s)")

def test_unlimited_extraction():
    """Test unlimited extraction (all posts)"""
    print("\n" + "=" * 70)
    print("🧪 TESTING UNLIMITED EXTRACTION")
    print("=" * 70)

    grabber = InstagramLinkGrabber(
        cookie_file='cookies/instagram.txt'
    )

    url = "https://www.instagram.com/anvil.anna"

    print(f"\n📥 Extracting ALL links from: {url}")
    print("⚠️ This may take a while...")

    start_time = time.time()
    links = grabber.extract_links(url, max_posts=0)  # 0 = unlimited
    elapsed = time.time() - start_time

    if links:
        print(f"\n✅ SUCCESS!")
        print(f"📊 Extracted: {len(links)} links")
        print(f"⏱️ Time taken: {elapsed:.2f} seconds")
        print(f"⚡ Speed: {len(links)/elapsed:.2f} links/second")

        grabber.save_to_file(links, 'test_output/anvil.anna_all.txt', 'anvil.anna')
    else:
        print(f"\n❌ FAILED")

if __name__ == '__main__':
    print("\n🚀 INSTAGRAM LINK GRABBER - TEST SUITE")
    print("=" * 70)

    # Run tests
    try:
        # Test 1: Single account (quick)
        test_single_account()

        # Test 2: Multiple accounts (medium)
        test_multiple_accounts()

        # Test 3: Unlimited extraction (slow)
        # Uncomment to test:
        # test_unlimited_extraction()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
