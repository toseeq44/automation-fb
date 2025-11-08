"""
IX Browser API Client
=====================
Handles all communication with IX Browser Cloud API.

Features:
- Profile listing
- Profile opening via API
- Profile closing via API
- Fallback to Local API if Cloud API fails
- Detailed logging at every step

API Documentation:
- Local API: http://localhost:35000
- Cloud API: https://api.ixbrowser.com/v2
"""
import logging
import requests
import time
from typing import Dict, List, Optional, Any


class IXAPIException(Exception):
    """Base exception for IX API errors"""
    pass


class AuthenticationError(IXAPIException):
    """API key authentication failed"""
    pass


class ProfileNotFoundError(IXAPIException):
    """Profile not found"""
    pass


class ProfileOpenError(IXAPIException):
    """Failed to open profile"""
    pass


class APIConnectionError(IXAPIException):
    """Cannot connect to API"""
    pass


class IXAPIClient:
    """
    IX Browser API Client for profile management

    Supports both Cloud API (with API key) and Local API (free).
    Automatically falls back to Local API if Cloud API is not available.
    """

    DEFAULT_BASE_URL = "http://localhost:35000"
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize IX API Client

        Args:
            api_key: API key for Cloud API (optional for Local API)
            base_url: API base URL (default: localhost:35000)
        """
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self._session = requests.Session()
        self._local_api_client = None  # Fallback to ixbrowser-local-api

        logging.info("="*60)
        logging.info("IX API CLIENT INITIALIZATION")
        logging.info("="*60)
        logging.info(f"📋 Base URL: {self.base_url}")

        # Set headers if API key provided
        if self.api_key:
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })
            logging.info("🔑 API Key: Provided (using Cloud API mode)")
        else:
            logging.info("🔑 API Key: Not provided (using Local API mode)")

        logging.info("✅ IX API Client initialized successfully")
        logging.info("="*60)
        logging.info("")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API with detailed logging

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            Response JSON data

        Raises:
            APIConnectionError: Connection failed
            IXAPIException: API returned error
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.DEFAULT_TIMEOUT)

        logging.info("")
        logging.info("─"*60)
        logging.info(f"API REQUEST: {method} {endpoint}")
        logging.info("─"*60)
        logging.debug(f"Full URL: {url}")

        if 'json' in kwargs:
            logging.debug(f"Request Body: {kwargs['json']}")

        try:
            start_time = time.time()
            response = self._session.request(method, url, **kwargs)
            elapsed = time.time() - start_time

            logging.info(f"📡 Response Status: {response.status_code}")
            logging.info(f"⏱️  Response Time: {elapsed:.2f}s")

            response.raise_for_status()

            data = response.json()

            # Check for API-specific error in response
            if isinstance(data, dict):
                code = data.get('code')
                if code is not None and code != 0:
                    error_msg = data.get('message', 'Unknown error')
                    logging.error(f"❌ API Error Code: {code}")
                    logging.error(f"❌ API Error Message: {error_msg}")
                    raise IXAPIException(f"API Error {code}: {error_msg}")

            logging.info("✅ Request successful")
            logging.info("─"*60)

            return data

        except requests.exceptions.ConnectionError as e:
            logging.error(f"❌ Connection Error: {e}")
            logging.error("⚠️  Make sure ixBrowser application is running")
            raise APIConnectionError(
                "Cannot connect to ixBrowser API. "
                "Make sure ixBrowser application is running."
            )
        except requests.exceptions.Timeout:
            logging.error(f"❌ Request Timeout (>{self.DEFAULT_TIMEOUT}s)")
            raise APIConnectionError("API request timeout")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logging.error("❌ Authentication Failed: Invalid API key")
                raise AuthenticationError("Invalid API key")
            logging.error(f"❌ HTTP Error: {e}")
            raise IXAPIException(f"HTTP Error: {e}")
        except ValueError as e:
            logging.error(f"❌ Invalid JSON Response: {e}")
            raise IXAPIException("Invalid JSON response from API")

    def _try_local_api_fallback(self):
        """Initialize local API client as fallback"""
        if self._local_api_client is not None:
            return self._local_api_client

        logging.info("")
        logging.info("⚠️  Attempting Local API fallback...")

        try:
            from ixbrowser_local_api import IXBrowserClient

            self._local_api_client = IXBrowserClient()
            logging.info("✅ Local API client initialized successfully")
            return self._local_api_client

        except ImportError:
            logging.error("❌ Local API not available")
            logging.error("Install with: pip install ixbrowser-local-api")
            return None

    def get_profile_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all profiles

        Returns:
            List of profile dictionaries

        Example Response:
            [
                {
                    "profile_id": "abc123",
                    "profile_name": "MyProfile1",
                    "browser_type": "chrome",
                    "status": "active"
                },
                ...
            ]
        """
        logging.info("")
        logging.info("="*60)
        logging.info("GETTING PROFILE LIST")
        logging.info("="*60)

        try:
            # Try Cloud/HTTP API first
            logging.info("📋 Method: Cloud/HTTP API")

            data = self._make_request("GET", "/api/v1/profile/list")

            if isinstance(data, dict) and 'data' in data:
                profiles = data['data']
            elif isinstance(data, list):
                profiles = data
            else:
                profiles = []

            logging.info("")
            logging.info(f"✅ Found {len(profiles)} profile(s)")

            for idx, profile in enumerate(profiles, 1):
                name = profile.get('profile_name', 'Unknown')
                pid = profile.get('profile_id', 'Unknown')
                logging.info(f"   {idx}. {name} (ID: {pid})")

            logging.info("="*60)

            return profiles

        except Exception as e:
            logging.warning(f"⚠️  Cloud API failed: {e}")

            # Fallback to Local API
            local_client = self._try_local_api_fallback()

            if not local_client:
                logging.error("❌ Both Cloud and Local API failed")
                raise IXAPIException("Cannot get profiles from any API")

            logging.info("📋 Method: Local API (Fallback)")

            try:
                profiles = local_client.get_profile_list()

                if profiles is None:
                    error_code = getattr(local_client, 'code', 'Unknown')
                    logging.error(f"❌ Local API Error Code: {error_code}")
                    raise IXAPIException(f"Local API Error: {error_code}")

                logging.info("")
                logging.info(f"✅ Found {len(profiles)} profile(s) via Local API")

                for idx, profile in enumerate(profiles, 1):
                    name = profile.get('profile_name', 'Unknown')
                    pid = profile.get('profile_id', 'Unknown')
                    logging.info(f"   {idx}. {name} (ID: {pid})")

                logging.info("="*60)

                return profiles

            except Exception as local_error:
                logging.error(f"❌ Local API also failed: {local_error}")
                raise IXAPIException(f"All API methods failed: {local_error}")

    def find_profile_by_name(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Find profile by name

        Args:
            profile_name: Profile name to search

        Returns:
            Profile dict if found, None otherwise
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"SEARCHING FOR PROFILE: {profile_name}")
        logging.info("="*60)

        profiles = self.get_profile_list()

        logging.info("")
        logging.info(f"🔍 Searching in {len(profiles)} profile(s)...")

        for profile in profiles:
            name = profile.get('profile_name', '')
            if name.lower() == profile_name.lower():
                profile_id = profile.get('profile_id')
                logging.info("")
                logging.info(f"✅ PROFILE FOUND!")
                logging.info(f"   Name: {name}")
                logging.info(f"   ID: {profile_id}")
                logging.info("="*60)
                return profile

        logging.error("")
        logging.error(f"❌ PROFILE NOT FOUND: {profile_name}")
        logging.info("="*60)
        return None

    def open_profile(
        self,
        profile_id: str,
        cookies_backup: bool = False
    ) -> Dict[str, Any]:
        """
        Open browser profile

        Args:
            profile_id: Profile ID to open
            cookies_backup: Whether to backup cookies

        Returns:
            {
                'webdriver': 'localhost:9222',
                'debugging_address': 'localhost:9222',
                'profile_id': 'abc123'
            }

        Raises:
            ProfileOpenError: Failed to open profile
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"OPENING PROFILE: {profile_id}")
        logging.info("="*60)
        logging.info(f"📋 Profile ID: {profile_id}")
        logging.info(f"📋 Cookies Backup: {cookies_backup}")

        try:
            # Try Cloud/HTTP API first
            logging.info("")
            logging.info("🚀 Method: Cloud/HTTP API")

            data = self._make_request(
                "POST",
                "/api/v1/profile/start",
                json={
                    "profile_id": profile_id,
                    "cookies_backup": cookies_backup
                }
            )

            if isinstance(data, dict) and 'data' in data:
                result = data['data']
            else:
                result = data

            webdriver = result.get('webdriver', 'Unknown')
            debug_addr = result.get('debugging_address', 'Unknown')

            logging.info("")
            logging.info("✅ PROFILE OPENED SUCCESSFULLY!")
            logging.info(f"   WebDriver Endpoint: {webdriver}")
            logging.info(f"   Debug Address: {debug_addr}")
            logging.info("="*60)

            return result

        except Exception as e:
            logging.warning(f"⚠️  Cloud API failed: {e}")

            # Fallback to Local API
            local_client = self._try_local_api_fallback()

            if not local_client:
                logging.error("❌ Both Cloud and Local API failed")
                raise ProfileOpenError("Cannot open profile via any API")

            logging.info("")
            logging.info("🚀 Method: Local API (Fallback)")

            try:
                result = local_client.open_profile(
                    profile_id,
                    cookies_backup=cookies_backup
                )

                if result is None:
                    error_code = getattr(local_client, 'code', 'Unknown')
                    logging.error(f"❌ Local API Error Code: {error_code}")
                    raise ProfileOpenError(f"Local API Error: {error_code}")

                webdriver = result.get('webdriver', 'Unknown')
                debug_addr = result.get('debugging_address', 'Unknown')

                logging.info("")
                logging.info("✅ PROFILE OPENED via Local API!")
                logging.info(f"   WebDriver Endpoint: {webdriver}")
                logging.info(f"   Debug Address: {debug_addr}")
                logging.info("="*60)

                return result

            except Exception as local_error:
                logging.error(f"❌ Local API also failed: {local_error}")
                raise ProfileOpenError(f"All API methods failed: {local_error}")

    def close_profile(self, profile_id: str) -> bool:
        """
        Close browser profile

        Args:
            profile_id: Profile ID to close

        Returns:
            True if successful
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"CLOSING PROFILE: {profile_id}")
        logging.info("="*60)

        try:
            logging.info("🔒 Method: Cloud/HTTP API")

            self._make_request(
                "POST",
                "/api/v1/profile/stop",
                json={"profile_id": profile_id}
            )

            logging.info("")
            logging.info("✅ PROFILE CLOSED SUCCESSFULLY")
            logging.info("="*60)
            return True

        except Exception as e:
            logging.error(f"❌ Failed to close profile: {e}")
            logging.warning("⚠️  Profile may still be open")
            return False
