#!/usr/bin/env python3
"""
Test script for Cookies Management System
Tests the new cookies functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.cookies_manager import CookiesManager
from PyQt5.QtWidgets import QApplication

def test_cookies_manager():
    """Test the cookies manager functionality"""
    print("🧪 Testing Cookies Manager...")
    
    # Initialize cookies manager
    cookies_manager = CookiesManager()
    
    # Test directory creation
    print(f"📁 Cookies directory: {cookies_manager.cookies_dir}")
    print(f"📁 Config directory: {cookies_manager.config_dir}")
    
    # Test cookie files paths
    print("\n📄 Cookie files:")
    for platform, filepath in cookies_manager.cookie_files.items():
        print(f"  {platform}: {filepath}")
    
    # Test platform domains
    print("\n🌐 Platform domains:")
    domains = cookies_manager.get_platform_domains()
    for platform, domain_list in domains.items():
        print(f"  {platform}: {', '.join(domain_list)}")
    
    # Test cookies status
    print("\n🔍 Checking cookies status...")
    status = cookies_manager.get_cookies_status()
    for platform, info in status.items():
        print(f"  {platform}: {'✅ Ready' if info['has_cookies'] and info['is_valid'] else '❌ Not ready'}")
    
    # Test cookie instructions
    print("\n📋 Cookie instructions for YouTube:")
    instructions = cookies_manager.get_cookie_instructions('youtube')
    print(instructions[:200] + "..." if len(instructions) > 200 else instructions)
    
    print("\n✅ Cookies Manager test completed!")

def test_manual_cookies():
    """Test manual cookie addition"""
    print("\n🧪 Testing Manual Cookie Addition...")
    
    cookies_manager = CookiesManager()
    
    # Test cookies
    test_cookies = {
        'sessionid': 'test_session_123',
        'csrftoken': 'test_csrf_456',
        'ds_user_id': 'test_user_789'
    }
    
    # Add test cookies for Instagram
    success = cookies_manager.add_manual_cookies('instagram', test_cookies)
    print(f"✅ Manual cookie addition: {'Success' if success else 'Failed'}")
    
    # Check if cookies were saved
    saved_cookies = cookies_manager.load_cookies('instagram')
    print(f"📊 Saved cookies count: {len(saved_cookies)}")
    
    # Test session update
    session = cookies_manager.session if hasattr(cookies_manager, 'session') else None
    if session:
        cookies_manager.update_session_with_cookies(session, 'instagram')
        print("✅ Session updated with cookies")
    
    print("✅ Manual cookies test completed!")

def test_cookie_instructions():
    """Test cookie instructions for all platforms"""
    print("\n🧪 Testing Cookie Instructions...")
    
    cookies_manager = CookiesManager()
    platforms = ['youtube', 'instagram', 'tiktok', 'facebook', 'twitter']
    
    for platform in platforms:
        print(f"\n📋 {platform.capitalize()} Instructions:")
        instructions = cookies_manager.get_cookie_instructions(platform)
        # Show first few lines
        lines = instructions.strip().split('\n')[:5]
        for line in lines:
            print(f"  {line}")
        print("  ...")
    
    print("\n✅ Cookie instructions test completed!")

if __name__ == "__main__":
    print("🚀 Cookies Management System Test Suite")
    print("=" * 50)
    
    try:
        test_cookies_manager()
    except Exception as e:
        print(f"❌ Cookies manager test failed: {e}")
    
    try:
        test_manual_cookies()
    except Exception as e:
        print(f"❌ Manual cookies test failed: {e}")
    
    try:
        test_cookie_instructions()
    except Exception as e:
        print(f"❌ Cookie instructions test failed: {e}")
    
    print("\n🎉 All tests completed!")
    print("\n📝 Next Steps:")
    print("1. Run the main application: python main.py")
    print("2. Go to Link Grabber module")
    print("3. Click '✏️ Add Manual' to add cookies")
    print("4. Follow the instructions to extract cookies from browser")
    print("5. Start extracting video links with cookies support!")
