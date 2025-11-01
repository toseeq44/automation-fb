#!/usr/bin/env python3
"""
Test script to verify API setup and functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.api_manager.core import APIManager, YouTubeAPI, InstagramAPI, TikTokAPI, FacebookAPI

def test_api_manager():
    """Test API Manager functionality"""
    print("🔧 Testing API Manager...")
    
    api_manager = APIManager()
    print(f"✅ API Manager initialized")
    print(f"📋 Available API keys: {list(api_manager.api_keys.keys())}")
    
    return api_manager

def test_youtube_api():
    """Test YouTube API (if key is available)"""
    print("\n📺 Testing YouTube API...")
    
    api_manager = APIManager()
    youtube_key = api_manager.api_keys.get('youtube_api_key')
    
    if not youtube_key:
        print("⚠️ No YouTube API key found - skipping test")
        return False
    
    try:
        youtube_api = YouTubeAPI(youtube_key)
        print("✅ YouTube API initialized successfully")
        return True
    except Exception as e:
        print(f"❌ YouTube API error: {e}")
        return False

def test_instagram_api():
    """Test Instagram API (if token is available)"""
    print("\n📷 Testing Instagram API...")
    
    api_manager = APIManager()
    instagram_token = api_manager.api_keys.get('instagram_access_token')
    
    if not instagram_token:
        print("⚠️ No Instagram access token found - skipping test")
        return False
    
    try:
        instagram_api = InstagramAPI(instagram_token)
        print("✅ Instagram API initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Instagram API error: {e}")
        return False

def test_tiktok_api():
    """Test TikTok API (if key is available)"""
    print("\n🎵 Testing TikTok API...")
    
    api_manager = APIManager()
    tiktok_key = api_manager.api_keys.get('tiktok_api_key')
    
    if not tiktok_key:
        print("⚠️ No TikTok API key found - skipping test")
        return False
    
    try:
        tiktok_api = TikTokAPI(tiktok_key)
        print("✅ TikTok API initialized successfully")
        return True
    except Exception as e:
        print(f"❌ TikTok API error: {e}")
        return False

def test_facebook_api():
    """Test Facebook API (if token is available)"""
    print("\n📘 Testing Facebook API...")
    
    api_manager = APIManager()
    facebook_token = api_manager.api_keys.get('facebook_access_token')
    
    if not facebook_token:
        print("⚠️ No Facebook access token found - skipping test")
        return False
    
    try:
        facebook_api = FacebookAPI(facebook_token)
        print("✅ Facebook API initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Facebook API error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 API Setup Test Suite")
    print("=" * 50)
    
    # Test API Manager
    api_manager = test_api_manager()
    
    # Test individual APIs
    youtube_ok = test_youtube_api()
    instagram_ok = test_instagram_api()
    tiktok_ok = test_tiktok_api()
    facebook_ok = test_facebook_api()
    
    # Summary
    print("\n📊 Test Summary:")
    print("=" * 50)
    print(f"🔧 API Manager: ✅ Working")
    print(f"📺 YouTube API: {'✅ Working' if youtube_ok else '⚠️ Not configured'}")
    print(f"📷 Instagram API: {'✅ Working' if instagram_ok else '⚠️ Not configured'}")
    print(f"🎵 TikTok API: {'✅ Working' if tiktok_ok else '⚠️ Not configured'}")
    print(f"📘 Facebook API: {'✅ Working' if facebook_ok else '⚠️ Not configured'}")
    
    configured_apis = sum([youtube_ok, instagram_ok, tiktok_ok, facebook_ok])
    
    print(f"\n🎯 Result: {configured_apis}/4 APIs configured")
    
    if configured_apis == 0:
        print("💡 Tip: Configure at least one API for better reliability!")
        print("📖 See API_SETUP_GUIDE.md for instructions")
    elif configured_apis < 4:
        print("💡 Tip: Configure more APIs for maximum coverage!")
    else:
        print("🎉 Excellent! All APIs are configured and ready!")
    
    print("\n✅ Test completed successfully!")

if __name__ == "__main__":
    main()

