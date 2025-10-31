"""
Facebook Auto Uploader - Upload Manager
Handles video upload logic, metadata, and Facebook interaction
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .utils import (
    get_video_files,
    load_video_metadata,
    format_file_size,
    record_upload,
    get_config_value
)


class UploadManager:
    """Manages Facebook video uploads"""

    def __init__(self, config: Dict, tracking_data: Dict, save_callback: Callable):
        """
        Initialize upload manager

        Args:
            config: Configuration dictionary
            tracking_data: Tracking data dictionary
            save_callback: Function to save tracking data
        """
        self.config = config
        self.tracking = tracking_data
        self.save_tracking = save_callback

    def upload_creator_videos(self, driver: webdriver.Chrome, creator_data: Dict):
        """
        Upload all videos for a creator

        Args:
            driver: Selenium WebDriver
            creator_data: Creator information dict
        """
        creator_name = creator_data['name']
        logging.info(f"Processing videos for: {creator_name}")

        # Get video files
        creator_path = Path(__file__).parent / 'creators' / creator_name
        videos = get_video_files(creator_path)

        if not videos:
            logging.info(f"No videos found for {creator_name}")
            return

        # Filter uploaded videos
        skip_uploaded = get_config_value(self.config, 'upload_settings.skip_uploaded', True)
        if skip_uploaded:
            videos = [v for v in videos if not self._is_uploaded(creator_name, v.name)]

        if not videos:
            logging.info(f"All videos already uploaded for {creator_name}")
            return

        logging.info(f"Found {len(videos)} video(s) to upload")

        # Upload each video
        for idx, video in enumerate(videos, 1):
            try:
                logging.info(f"[{idx}/{len(videos)}] Uploading: {video.name}")
                self.single_upload(driver, creator_data, video, creator_path)

                # Wait between videos
                if idx < len(videos):
                    wait_time = get_config_value(self.config, 'upload_settings.wait_between_videos', 120)
                    logging.info(f"Waiting {wait_time}s before next video...")
                    time.sleep(wait_time)

            except Exception as e:
                logging.error(f"Failed to upload {video.name}: {e}")
                record_upload(
                    self.tracking,
                    creator_name,
                    video.name,
                    'failed',
                    creator_data.get('profile_name', ''),
                    str(e)
                )
                self.save_tracking()
                continue

    def single_upload(self, driver: webdriver.Chrome, creator_data: Dict,
                     video_path: Path, creator_path: Path):
        """
        Upload a single video to Facebook

        Args:
            driver: Selenium WebDriver
            creator_data: Creator information
            video_path: Path to video file
            creator_path: Path to creator folder
        """
        creator_name = creator_data['name']
        logging.info(f"Uploading: {video_path.name} ({format_file_size(video_path.stat().st_size)})")

        try:
            # Navigate to upload page
            upload_url = self._get_upload_url(creator_data.get('page_id', ''))
            logging.info(f"Navigating to: {upload_url}")
            driver.get(upload_url)
            time.sleep(5)

            # Check if login needed
            if self._needs_login(driver):
                logging.info("Login required")
                if not self._handle_login(driver, creator_data):
                    raise Exception("Login failed")

                driver.get(upload_url)
                time.sleep(5)

            # Perform upload
            self._perform_upload(driver, video_path, creator_path)

            # Record success
            record_upload(
                self.tracking,
                creator_name,
                video_path.name,
                'completed',
                creator_data.get('profile_name', '')
            )
            self.save_tracking()

            logging.info(f"✓ Successfully uploaded: {video_path.name}")

            # Delete if configured
            if get_config_value(self.config, 'upload_settings.delete_after_upload', False):
                video_path.unlink()
                logging.info(f"Deleted: {video_path.name}")

            # Wait after upload
            wait_time = get_config_value(self.config, 'upload_settings.wait_after_upload', 30)
            time.sleep(wait_time)

        except Exception as e:
            logging.error(f"Upload failed: {e}")
            record_upload(
                self.tracking,
                creator_name,
                video_path.name,
                'failed',
                creator_data.get('profile_name', ''),
                str(e)
            )
            self.save_tracking()
            raise

    def _perform_upload(self, driver: webdriver.Chrome, video_path: Path, creator_path: Path):
        """Perform the actual upload process"""
        # Load metadata
        metadata = load_video_metadata(creator_path, video_path.name)

        # Click create video button
        self._click_create_video_button(driver)

        # Find file input
        file_input = self._find_file_input(driver)
        if not file_input:
            raise Exception("Could not find file input element")

        # Upload file
        logging.info("Uploading file...")
        file_input.send_keys(str(video_path.absolute()))
        time.sleep(5)

        # Fill metadata
        self._fill_metadata(driver, metadata)

        # Wait for upload
        self._wait_for_upload_complete(driver)

        # Click publish
        self._click_publish_button(driver)
        time.sleep(10)

    def _click_create_video_button(self, driver: webdriver.Chrome):
        """Click the create video button"""
        selectors = [
            "//span[contains(text(), 'Create video')]",
            "//span[contains(text(), 'Upload video')]",
            "//div[@aria-label='Create video']",
            "//button[contains(text(), 'Create')]",
        ]

        for selector in selectors:
            try:
                element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                element.click()
                time.sleep(3)
                return
            except TimeoutException:
                continue

    def _find_file_input(self, driver: webdriver.Chrome, timeout: int = 30):
        """Find file upload input element"""
        selectors = [
            "input[type='file']",
            "input[accept*='video']",
            "//input[@type='file']",
        ]

        for selector in selectors:
            try:
                by_type = By.CSS_SELECTOR if not selector.startswith('//') else By.XPATH
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by_type, selector))
                )
                return element
            except TimeoutException:
                continue

        # Make hidden input visible
        try:
            driver.execute_script("""
                var inputs = document.querySelectorAll('input[type=file]');
                for(var i = 0; i < inputs.length; i++) {
                    inputs[i].style.display = 'block';
                    inputs[i].style.visibility = 'visible';
                }
            """)
            time.sleep(2)
            return driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        except:
            return None

    def _fill_metadata(self, driver: webdriver.Chrome, metadata: Dict):
        """Fill in video metadata"""
        # Fill title
        title = metadata.get('title', '')
        if title:
            title_selectors = [
                "//input[@placeholder*='Title']",
                "input[aria-label*='Title']",
            ]
            for selector in title_selectors:
                try:
                    by_type = By.XPATH if selector.startswith('//') else By.CSS_SELECTOR
                    field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                    field.clear()
                    field.send_keys(title)
                    logging.info(f"Set title: {title}")
                    break
                except TimeoutException:
                    continue

        # Fill description
        description = metadata.get('description', '')
        if description:
            desc_selectors = [
                "//textarea[@placeholder*='Description']",
                "textarea[aria-label*='Description']",
            ]
            for selector in desc_selectors:
                try:
                    by_type = By.XPATH if selector.startswith('//') else By.CSS_SELECTOR
                    field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                    field.clear()
                    field.send_keys(description)
                    logging.info("Set description")
                    break
                except TimeoutException:
                    continue

    def _wait_for_upload_complete(self, driver: webdriver.Chrome):
        """Wait for video upload and processing"""
        max_wait = get_config_value(self.config, 'upload_settings.upload_timeout', 600)
        start_time = time.time()

        logging.info("Waiting for upload to complete...")

        while time.time() - start_time < max_wait:
            try:
                # Check progress bar
                try:
                    progress = driver.find_element(By.CSS_SELECTOR, "[role='progressbar']")
                    progress_value = progress.get_attribute('aria-valuenow')
                    if progress_value and int(progress_value) >= 100:
                        time.sleep(5)
                        break
                except:
                    pass

                # Check for completion message
                try:
                    driver.find_element(By.XPATH, "//*[contains(text(), 'Upload complete')]")
                    break
                except:
                    pass

                time.sleep(5)

            except Exception as e:
                time.sleep(5)

    def _click_publish_button(self, driver: webdriver.Chrome):
        """Click the publish button"""
        button_texts = ['Publish', 'Post', 'Share']

        for text in button_texts:
            try:
                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{text}')]/ancestor::button"))
                )
                button.click()
                logging.info(f"Clicked '{text}' button")
                return
            except TimeoutException:
                continue

    def _needs_login(self, driver: webdriver.Chrome) -> bool:
        """Check if login is required"""
        current_url = driver.current_url.lower()
        login_indicators = ['login', 'signin', 'authenticate']

        if any(indicator in current_url for indicator in login_indicators):
            return True

        try:
            driver.find_element(By.ID, "email")
            return True
        except:
            return False

    def _handle_login(self, driver: webdriver.Chrome, creator_data: Dict) -> bool:
        """Handle Facebook login"""
        logging.info("Handling login...")

        try:
            email = creator_data.get('facebook_email', '')
            password = creator_data.get('facebook_password', '')

            if not email or not password:
                return False

            # Fill email
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_field.clear()
            email_field.send_keys(email)

            # Fill password
            password_field = driver.find_element(By.ID, "pass")
            password_field.clear()
            password_field.send_keys(password)

            # Click login
            try:
                login_button = driver.find_element(By.NAME, "login")
                login_button.click()
            except:
                password_field.send_keys(Keys.RETURN)

            # Wait for login
            wait_time = get_config_value(self.config, 'facebook.wait_for_login', 20)
            time.sleep(wait_time)

            # Check if still on login page (might need 2FA)
            if self._needs_login(driver):
                logging.warning("Login requires verification - waiting...")
                for _ in range(150):  # Wait up to 5 minutes
                    time.sleep(2)
                    if not self._needs_login(driver):
                        return True
                return False

            return True

        except Exception as e:
            logging.error(f"Login failed: {e}")
            return False

    def _get_upload_url(self, page_id: str = '') -> str:
        """Get Facebook upload URL"""
        if page_id:
            return f"https://www.facebook.com/{page_id}/videos"
        return get_config_value(self.config, 'facebook.video_upload_url', 'https://www.facebook.com/')

    def _is_uploaded(self, creator_name: str, video_name: str) -> bool:
        """Check if video was uploaded"""
        history = self.tracking.get('upload_history', [])
        for entry in history:
            if (entry.get('creator_name') == creator_name and
                entry.get('video_file') == video_name and
                entry.get('status') == 'completed'):
                return True
        return False
