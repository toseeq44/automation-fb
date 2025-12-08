"""
Cookies Manager for Social Media Platforms
Handles browser cookies for bypassing anti-bot protection
"""

import json
import os
import sys
import pickle
import requests
from pathlib import Path
from typing import Dict, List, Optional
from PyQt5.QtWidgets import QMessageBox, QFileDialog

class CookiesManager:
    """Manages cookies for different social media platforms"""
    
    def __init__(self, project_root: str = None):
        if project_root:
            self.project_root = project_root
        else:
            # Determine correct root path (handles EXE vs Script)
            if getattr(sys, 'frozen', False):
                self.project_root = os.path.dirname(sys.executable)
            else:
                self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.cookies_dir = os.path.join(self.project_root, "cookies")
        self.config_dir = os.path.join(self.project_root, "config")
        
        # Ensure directories exist
        try:
            os.makedirs(self.cookies_dir, exist_ok=True)
            os.makedirs(self.config_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create directories: {e}")

        
        # Platform-specific cookie files
        self.cookie_files = {
            'youtube': os.path.join(self.cookies_dir, 'youtube_cookies.pkl'),
            'instagram': os.path.join(self.cookies_dir, 'instagram_cookies.pkl'),
            'tiktok': os.path.join(self.cookies_dir, 'tiktok_cookies.pkl'),
            'facebook': os.path.join(self.cookies_dir, 'facebook_cookies.pkl'),
            'twitter': os.path.join(self.cookies_dir, 'twitter_cookies.pkl')
        }
        
        # Load existing cookies
        self.cookies = self.load_all_cookies()
    
    def get_browser_cookies(self, domain: str) -> Dict:
        """Extract cookies from browser for specific domain"""
        # Manual cookie extraction - user needs to provide cookies
        # This is a placeholder for manual cookie input
        return {}
    
    def save_cookies(self, platform: str, cookies: Dict):
        """Save cookies for a specific platform"""
        try:
            with open(self.cookie_files[platform], 'wb') as f:
                pickle.dump(cookies, f)
            print(f"✅ Saved cookies for {platform}")
        except Exception as e:
            print(f"❌ Failed to save cookies for {platform}: {e}")
    
    def load_cookies(self, platform: str) -> Dict:
        """Load cookies for a specific platform"""
        try:
            if os.path.exists(self.cookie_files[platform]):
                with open(self.cookie_files[platform], 'rb') as f:
                    cookies = pickle.load(f)
                print(f"✅ Loaded cookies for {platform}")
                return cookies
            else:
                print(f"⚠️ No cookies found for {platform}")
                return {}
        except Exception as e:
            print(f"❌ Failed to load cookies for {platform}: {e}")
            return {}
    
    def load_all_cookies(self) -> Dict:
        """Load all platform cookies"""
        all_cookies = {}
        for platform in self.cookie_files.keys():
            all_cookies[platform] = self.load_cookies(platform)
        return all_cookies
    
    def get_platform_domains(self) -> Dict[str, List[str]]:
        """Get domains for each platform"""
        return {
            'youtube': ['youtube.com', '.youtube.com', 'youtu.be'],
            'instagram': ['instagram.com', '.instagram.com'],
            'tiktok': ['tiktok.com', '.tiktok.com'],
            'facebook': ['facebook.com', '.facebook.com', 'fb.watch'],
            'twitter': ['twitter.com', '.twitter.com', 'x.com', '.x.com']
        }
    
    def extract_platform_cookies(self, platform: str) -> Dict:
        """Extract cookies from browser for specific platform"""
        domains = self.get_platform_domains().get(platform, [])
        all_cookies = {}
        
        for domain in domains:
            cookies = self.get_browser_cookies(domain)
            all_cookies.update(cookies)
        
        return all_cookies
    
    def setup_cookies_for_platform(self, platform: str) -> bool:
        """Setup cookies for a specific platform"""
        try:
            print(f"🔍 Setting up cookies for {platform}...")
            cookies = self.extract_platform_cookies(platform)
            
            if cookies:
                self.save_cookies(platform, cookies)
                self.cookies[platform] = cookies
                print(f"✅ Successfully setup {len(cookies)} cookies for {platform}")
                return True
            else:
                print(f"⚠️ No cookies found for {platform}. Please add cookies manually.")
                return False
        except Exception as e:
            print(f"❌ Failed to setup cookies for {platform}: {e}")
            return False
    
    def add_manual_cookies(self, platform: str, cookies_dict: Dict) -> bool:
        """Add cookies manually for a platform"""
        try:
            if cookies_dict:
                self.save_cookies(platform, cookies_dict)
                self.cookies[platform] = cookies_dict
                print(f"✅ Successfully added {len(cookies_dict)} cookies for {platform}")
                return True
            else:
                print(f"⚠️ No cookies provided for {platform}")
                return False
        except Exception as e:
            print(f"❌ Failed to add cookies for {platform}: {e}")
            return False
    
    def get_cookie_instructions(self, platform: str) -> str:
        """Get instructions for extracting cookies for a platform"""
        instructions = {
            'youtube': """
🍪 YouTube Cookies Setup:

1. Open Chrome/Firefox and go to youtube.com
2. Login to your YouTube account
3. Press F12 to open Developer Tools
4. Go to Application/Storage tab
5. Click on Cookies → https://www.youtube.com
6. Copy the following cookies:
   - session_token
   - __Secure-1PSID
   - __Secure-3PSID
   - VISITOR_INFO1_LIVE
   - YSC
   - PREF

7. Paste them in format: cookie_name=cookie_value
            """,
            'instagram': """
🍪 Instagram Cookies Setup:

1. Open Chrome/Firefox and go to instagram.com
2. Login to your Instagram account
3. Press F12 to open Developer Tools
4. Go to Application/Storage tab
5. Click on Cookies → https://www.instagram.com
6. Copy the following cookies:
   - sessionid
   - csrftoken
   - ds_user_id
   - mid
   - rur

7. Paste them in format: cookie_name=cookie_value
            """,
            'tiktok': """
🍪 TikTok Cookies Setup:

1. Open Chrome/Firefox and go to tiktok.com
2. Login to your TikTok account
3. Press F12 to open Developer Tools
4. Go to Application/Storage tab
5. Click on Cookies → https://www.tiktok.com
6. Copy the following cookies:
   - sessionid
   - msToken
   - ttwid
   - odin_tt
   - passport_csrf_token

7. Paste them in format: cookie_name=cookie_value
            """,
            'facebook': """
🍪 Facebook Cookies Setup:

1. Open Chrome/Firefox and go to facebook.com
2. Login to your Facebook account
3. Press F12 to open Developer Tools
4. Go to Application/Storage tab
5. Click on Cookies → https://www.facebook.com
6. Copy the following cookies:
   - c_user
   - xs
   - fr
   - datr
   - sb

7. Paste them in format: cookie_name=cookie_value
            """,
            'twitter': """
🍪 Twitter/X Cookies Setup:

1. Open Chrome/Firefox and go to twitter.com or x.com
2. Login to your Twitter/X account
3. Press F12 to open Developer Tools
4. Go to Application/Storage tab
5. Click on Cookies → https://twitter.com
6. Copy the following cookies:
   - auth_token
   - ct0
   - guest_id
   - personalization_id
   - twid

7. Paste them in format: cookie_name=cookie_value
            """
        }
        return instructions.get(platform, "No specific instructions available.")
    
    def setup_all_cookies(self) -> Dict[str, bool]:
        """Setup cookies for all platforms"""
        results = {}
        for platform in self.cookie_files.keys():
            results[platform] = self.setup_cookies_for_platform(platform)
        return results
    
    def get_cookies_for_session(self, platform: str) -> requests.cookies.RequestsCookieJar:
        """Get cookies formatted for requests session"""
        cookies = self.cookies.get(platform, {})
        cookie_jar = requests.cookies.RequestsCookieJar()
        
        for name, value in cookies.items():
            cookie_jar.set(name, value)
        
        return cookie_jar
    
    def update_session_with_cookies(self, session: requests.Session, platform: str):
        """Update requests session with platform cookies"""
        cookie_jar = self.get_cookies_for_session(platform)
        session.cookies.update(cookie_jar)
        
        # Add common headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def check_cookies_validity(self, platform: str) -> bool:
        """Check if cookies are still valid"""
        try:
            cookies = self.cookies.get(platform, {})
            if not cookies:
                return False
            
            # Test with a simple request
            session = requests.Session()
            self.update_session_with_cookies(session, platform)
            
            test_urls = {
                'youtube': 'https://www.youtube.com',
                'instagram': 'https://www.instagram.com',
                'tiktok': 'https://www.tiktok.com',
                'facebook': 'https://www.facebook.com',
                'twitter': 'https://twitter.com'
            }
            
            response = session.get(test_urls.get(platform, ''), timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Cookies validity check failed for {platform}: {e}")
            return False
    
    def get_cookies_status(self) -> Dict[str, Dict]:
        """Get status of all platform cookies"""
        status = {}
        for platform in self.cookie_files.keys():
            cookies = self.cookies.get(platform, {})
            status[platform] = {
                'has_cookies': len(cookies) > 0,
                'cookie_count': len(cookies),
                'is_valid': self.check_cookies_validity(platform) if cookies else False
            }
        return status
    
    def clear_cookies(self, platform: str = None):
        """Clear cookies for platform or all platforms"""
        if platform:
            try:
                if os.path.exists(self.cookie_files[platform]):
                    os.remove(self.cookie_files[platform])
                self.cookies[platform] = {}
                print(f"✅ Cleared cookies for {platform}")
            except Exception as e:
                print(f"❌ Failed to clear cookies for {platform}: {e}")
        else:
            # Clear all cookies
            for platform in self.cookie_files.keys():
                self.clear_cookies(platform)
    
    def export_cookies(self, platform: str, filepath: str):
        """Export cookies to JSON file"""
        try:
            cookies = self.cookies.get(platform, {})
            with open(filepath, 'w') as f:
                json.dump(cookies, f, indent=2)
            print(f"✅ Exported cookies for {platform} to {filepath}")
        except Exception as e:
            print(f"❌ Failed to export cookies for {platform}: {e}")
    
    def import_cookies(self, platform: str, filepath: str):
        """Import cookies from JSON file"""
        try:
            with open(filepath, 'r') as f:
                cookies = json.load(f)
            self.save_cookies(platform, cookies)
            self.cookies[platform] = cookies
            print(f"✅ Imported cookies for {platform} from {filepath}")
        except Exception as e:
            print(f"❌ Failed to import cookies for {platform}: {e}")


class CookiesSetupDialog:
    """GUI dialog for setting up cookies"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.cookies_manager = CookiesManager()
    
    def show_setup_instructions(self):
        """Show instructions for setting up cookies"""
        instructions = """
🍪 Cookies Setup Instructions

To extract video links successfully, you need to login to each platform in your browser first:

1. 📺 YouTube:
   - Open Chrome/Firefox
   - Go to youtube.com
   - Login with your account
   - Keep browser open

2. 📷 Instagram:
   - Go to instagram.com
   - Login with your account
   - Keep browser open

3. 🎵 TikTok:
   - Go to tiktok.com
   - Login with your account
   - Keep browser open

4. 📘 Facebook:
   - Go to facebook.com
   - Login with your account
   - Keep browser open

5. 🐦 Twitter/X:
   - Go to twitter.com or x.com
   - Login with your account
   - Keep browser open

After logging in, click "Extract Cookies" to automatically get cookies from your browser.

⚠️ Important:
- Keep your browser open while extracting
- Don't logout from platforms
- Cookies will be saved locally for future use
        """
        
        if self.parent:
            QMessageBox.information(self.parent, "Cookies Setup", instructions)
        else:
            print(instructions)
    
    def extract_all_cookies(self) -> Dict[str, bool]:
        """Extract cookies for all platforms"""
        return self.cookies_manager.setup_all_cookies()
    
    def get_cookies_status(self) -> Dict[str, Dict]:
        """Get cookies status for all platforms"""
        return self.cookies_manager.get_cookies_status()
