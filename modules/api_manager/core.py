"""
modules/api_manager/core.py
ENHANCED: Multi-API approach with official APIs + yt-dlp fallback
Best error-free approach for all platforms
"""

import os
import json
import requests
from PyQt5.QtCore import QThread, pyqtSignal
import yt_dlp
from typing import Dict, List, Optional, Tuple


class APIManager:
    """Centralized API management for all platforms"""
    
    def __init__(self):
        self.api_keys = self.load_api_keys()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def load_api_keys(self) -> Dict[str, str]:
        """Load API keys from config file"""
        config_file = "api_config.json"
        default_keys = {
            "youtube_api_key": "",
            "instagram_access_token": "",
            "tiktok_api_key": "",
            "facebook_access_token": ""
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Create default config
        with open(config_file, 'w') as f:
            json.dump(default_keys, f, indent=2)
        
        return default_keys
    
    def save_api_keys(self):
        """Save API keys to config file"""
        with open("api_config.json", 'w') as f:
            json.dump(self.api_keys, f, indent=2)


class YouTubeAPI:
    """YouTube Data API v3 integration"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    def get_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict]:
        """Get videos from YouTube channel using official API"""
        try:
            # Get channel's uploads playlist
            channel_url = f"{self.base_url}/channels"
            params = {
                'part': 'contentDetails',
                'id': channel_id,
                'key': self.api_key
            }
            
            response = requests.get(channel_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('items'):
                return []
            
            uploads_playlist = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            playlist_url = f"{self.base_url}/playlistItems"
            params = {
                'part': 'snippet',
                'playlistId': uploads_playlist,
                'maxResults': max_results,
                'key': self.api_key
            }
            
            response = requests.get(playlist_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            videos = []
            
            for item in data.get('items', []):
                video_id = item['snippet']['resourceId']['videoId']
                title = item['snippet']['title']
                published = item['snippet']['publishedAt']
                
                videos.append({
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'title': title,
                    'published': published,
                    'type': 'YouTube Video',
                    'source': 'youtube_api'
                })
            
            return videos
            
        except Exception as e:
            print(f"YouTube API Error: {e}")
            return []
    
    def get_playlist_videos(self, playlist_id: str, max_results: int = 50) -> List[Dict]:
        """Get videos from YouTube playlist using official API"""
        try:
            url = f"{self.base_url}/playlistItems"
            params = {
                'part': 'snippet',
                'playlistId': playlist_id,
                'maxResults': max_results,
                'key': self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            videos = []
            
            for item in data.get('items', []):
                video_id = item['snippet']['resourceId']['videoId']
                title = item['snippet']['title']
                
                videos.append({
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'title': title,
                    'type': 'YouTube Video',
                    'source': 'youtube_api'
                })
            
            return videos
            
        except Exception as e:
            print(f"YouTube API Error: {e}")
            return []


class InstagramAPI:
    """Instagram Basic Display API integration"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://graph.instagram.com"
    
    def get_user_media(self, user_id: str, limit: int = 25) -> List[Dict]:
        """Get user's media using Instagram API"""
        try:
            url = f"{self.base_url}/{user_id}/media"
            params = {
                'fields': 'id,caption,media_type,media_url,thumbnail_url,timestamp',
                'limit': limit,
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            videos = []
            
            for item in data.get('data', []):
                if item.get('media_type') in ['VIDEO', 'CAROUSEL_ALBUM']:
                    videos.append({
                        'url': item.get('media_url', ''),
                        'title': item.get('caption', 'Instagram Video')[:100],
                        'type': 'Instagram Video',
                        'source': 'instagram_api',
                        'timestamp': item.get('timestamp')
                    })
            
            return videos
            
        except Exception as e:
            print(f"Instagram API Error: {e}")
            return []


class TikTokAPI:
    """TikTok Research API integration"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://open.tiktokapis.com/v2"
    
    def get_user_videos(self, username: str, max_count: int = 20) -> List[Dict]:
        """Get user's videos using TikTok Research API"""
        try:
            url = f"{self.base_url}/research/user/video/query/"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'query': {
                    'and': [
                        {
                            'operation': 'EQ',
                            'field_name': 'username',
                            'field_values': [username]
                        }
                    ]
                },
                'max_count': max_count,
                'start_date': '2020-01-01',
                'end_date': '2024-12-31'
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            videos = []
            
            for item in result.get('data', {}).get('videos', []):
                videos.append({
                    'url': item.get('video_url', ''),
                    'title': item.get('title', 'TikTok Video'),
                    'type': 'TikTok',
                    'source': 'tiktok_api',
                    'view_count': item.get('view_count', 0)
                })
            
            return videos
            
        except Exception as e:
            print(f"TikTok API Error: {e}")
            return []


class FacebookAPI:
    """Facebook Graph API integration"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def get_page_videos(self, page_id: str, limit: int = 25) -> List[Dict]:
        """Get page's videos using Facebook Graph API"""
        try:
            url = f"{self.base_url}/{page_id}/videos"
            params = {
                'fields': 'id,description,created_time,source,length',
                'limit': limit,
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            videos = []
            
            for item in data.get('data', []):
                videos.append({
                    'url': item.get('source', ''),
                    'title': item.get('description', 'Facebook Video')[:100],
                    'type': 'Facebook Video',
                    'source': 'facebook_api',
                    'created_time': item.get('created_time')
                })
            
            return videos
            
        except Exception as e:
            print(f"Facebook API Error: {e}")
            return []


class EnhancedLinkGrabberThread(QThread):
    """Enhanced link grabber with API-first approach + yt-dlp fallback"""
    
    # Signals
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)
    
    def __init__(self, url: str, options: Dict):
        super().__init__()
        self.url = url
        self.options = options
        self.is_cancelled = False
        self.found_links = []
        self.api_manager = APIManager()
    
    def run(self):
        """Main extraction with API-first approach"""
        try:
            self.progress.emit("🔍 Analyzing URL with enhanced API approach...")
            self.progress_percent.emit(5)
            
            # Try API approach first
            api_links = self.try_api_extraction()
            
            if api_links:
                self.progress.emit(f"✅ API extraction successful! Found {len(api_links)} links")
                self.found_links = api_links
                self.progress_percent.emit(100)
                self.finished.emit(True, f"✅ API Success: {len(api_links)} links extracted", api_links)
                return
            
            # Fallback to yt-dlp if API fails
            self.progress.emit("⚠️ API failed, using yt-dlp fallback...")
            yt_dlp_links = self.try_yt_dlp_extraction()
            
            if yt_dlp_links:
                self.progress.emit(f"✅ yt-dlp fallback successful! Found {len(yt_dlp_links)} links")
                self.found_links = yt_dlp_links
                self.progress_percent.emit(100)
                self.finished.emit(True, f"✅ Fallback Success: {len(yt_dlp_links)} links extracted", yt_dlp_links)
            else:
                self.finished.emit(False, "❌ Both API and yt-dlp failed", [])
        
        except Exception as e:
            self.finished.emit(False, f"❌ Error: {str(e)}", [])
    
    def try_api_extraction(self) -> List[Dict]:
        """Try extracting using official APIs first"""
        try:
            url_lower = self.url.lower()
            
            # YouTube API
            if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
                return self.extract_youtube_api()
            
            # Instagram API
            elif 'instagram.com' in url_lower:
                return self.extract_instagram_api()
            
            # TikTok API
            elif 'tiktok.com' in url_lower:
                return self.extract_tiktok_api()
            
            # Facebook API
            elif 'facebook.com' in url_lower:
                return self.extract_facebook_api()
            
            return []
            
        except Exception as e:
            print(f"API extraction error: {e}")
            return []
    
    def extract_youtube_api(self) -> List[Dict]:
        """Extract YouTube videos using official API"""
        api_key = self.api_manager.api_keys.get('youtube_api_key')
        if not api_key:
            return []
        
        youtube_api = YouTubeAPI(api_key)
        
        # Extract channel ID or playlist ID from URL
        if '/channel/' in self.url:
            channel_id = self.url.split('/channel/')[-1].split('/')[0]
            return youtube_api.get_channel_videos(channel_id, self.options.get('max_videos', 50))
        
        elif '/playlist' in self.url:
            playlist_id = self.url.split('list=')[-1].split('&')[0]
            return youtube_api.get_playlist_videos(playlist_id, self.options.get('max_videos', 50))
        
        return []
    
    def extract_instagram_api(self) -> List[Dict]:
        """Extract Instagram videos using official API"""
        access_token = self.api_manager.api_keys.get('instagram_access_token')
        if not access_token:
            return []
        
        # Extract username from URL
        username = self.url.split('/')[-1].split('?')[0]
        if username.startswith('@'):
            username = username[1:]
        
        instagram_api = InstagramAPI(access_token)
        return instagram_api.get_user_media(username, self.options.get('max_videos', 25))
    
    def extract_tiktok_api(self) -> List[Dict]:
        """Extract TikTok videos using official API"""
        api_key = self.api_manager.api_keys.get('tiktok_api_key')
        if not api_key:
            return []
        
        # Extract username from URL
        username = self.url.split('/')[-1].split('?')[0]
        if username.startswith('@'):
            username = username[1:]
        
        tiktok_api = TikTokAPI(api_key)
        return tiktok_api.get_user_videos(username, self.options.get('max_videos', 20))
    
    def extract_facebook_api(self) -> List[Dict]:
        """Extract Facebook videos using official API"""
        access_token = self.api_manager.api_keys.get('facebook_access_token')
        if not access_token:
            return []
        
        # Extract page ID from URL
        page_id = self.url.split('/')[-1].split('?')[0]
        
        facebook_api = FacebookAPI(access_token)
        return facebook_api.get_page_videos(page_id, self.options.get('max_videos', 25))
    
    def try_yt_dlp_extraction(self) -> List[Dict]:
        """Fallback to yt-dlp extraction"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'skip_download': True,
            }
            
            if self.options.get('max_videos', 0) > 0:
                ydl_opts['playlistend'] = self.options['max_videos']
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                
                links = []
                if 'entries' in info:
                    for entry in info['entries']:
                        if entry:
                            links.append({
                                'url': entry.get('webpage_url', ''),
                                'title': entry.get('title', 'Unknown'),
                                'type': 'Video',
                                'source': 'yt_dlp_fallback'
                            })
                else:
                    links.append({
                        'url': info.get('webpage_url', ''),
                        'title': info.get('title', 'Unknown'),
                        'type': 'Video',
                        'source': 'yt_dlp_fallback'
                    })
                
                return links
                
        except Exception as e:
            print(f"yt-dlp fallback error: {e}")
            return []
    
    def cancel(self):
        """Cancel extraction"""
        self.is_cancelled = True
        self.progress.emit("⚠️ Cancelling extraction...")

