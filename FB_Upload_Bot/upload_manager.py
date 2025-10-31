"""
Facebook Upload Bot - Upload Manager
Handles video upload logic, metadata, and Facebook interaction
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException

from utils import get_video_files, format_file_size


class UploadManager:
    """Manages Facebook video uploads"""

    def __init__(self, config, db_manager):
        """
        Initialize upload manager

        Args:
            config: ConfigLoader instance
            db_manager: DatabaseManager instance
        """
        self.config = config
        self.db = db_manager

    def upload_creator_videos(self, driver: webdriver.Chrome, creator_data: Dict, profile_id: int):
        """
        Upload all videos for a creator

        Args:
            driver: Selenium WebDriver
            creator_data: Creator information dict
            profile_id: Profile ID in database
        """
        creator_name = creator_data['name']
        logging.info(f"Processing videos for creator: {creator_name}")

        # Get video files
        videos = self.get_creator_videos(creator_name)

        if not videos:
            logging.info(f"No videos found for {creator_name}")
            return

        # Filter out already uploaded videos
        if self.config.get('upload_settings.skip_uploaded', True):
            videos = [v for v in videos if not self.db.is_video_uploaded(creator_name, v.name)]

        if not videos:
            logging.info(f"All videos already uploaded for {creator_name}")
            return

        logging.info(f"Found {len(videos)} video(s) to upload for {creator_name}")

        # Upload each video
        for idx, video in enumerate(videos, 1):
            try:
                logging.info(f"[{idx}/{len(videos)}] Uploading: {video.name}")
                self.single_upload(driver, creator_data, video, profile_id)

                # Wait between videos
                if idx < len(videos):
                    wait_time = self.config.get('upload_settings.wait_between_videos', 120)
                    logging.info(f"Waiting {wait_time} seconds before next video...")
                    time.sleep(wait_time)

            except Exception as e:
                logging.error(f"Failed to upload {video.name}: {e}")
                self.db.record_upload(creator_name, video.name, 'failed', profile_id, str(e))
                continue

    def get_creator_videos(self, creator_name: str) -> List[Path]:
        """
        Get list of videos for a creator

        Args:
            creator_name: Creator folder name

        Returns:
            List of video file paths
        """
        creators_folder = Path(self.config.get('paths.creators_folder'))
        creator_path = creators_folder / creator_name

        if not creator_path.exists():
            logging.warning(f"Creator folder not found: {creator_path}")
            return []

        return get_video_files(creator_path)

    def single_upload(self, driver: webdriver.Chrome, creator_data: Dict, video_path: Path, profile_id: int):
        """
        Upload a single video to Facebook

        Args:
            driver: Selenium WebDriver
            creator_data: Creator information
            video_path: Path to video file
            profile_id: Profile ID
        """
        creator_name = creator_data['name']
        page_id = creator_data.get('page_id', '')
        page_name = creator_data.get('page_name', '')

        logging.info(f"Uploading: {video_path.name} ({format_file_size(video_path.stat().st_size)})")

        # Record upload attempt
        self.db.record_upload(creator_name, video_path.name, 'uploading', profile_id)

        try:
            # Navigate to upload page
            upload_url = self.get_upload_url(page_id)
            logging.info(f"Navigating to: {upload_url}")
            driver.get(upload_url)
            time.sleep(5)

            # Check if login needed
            if self.needs_login(driver):
                logging.info("Login required")
                if not self.handle_login(driver, creator_data):
                    raise Exception("Login failed")

                # Navigate again after login
                driver.get(upload_url)
                time.sleep(5)

            # Perform upload
            self.perform_upload(driver, video_path, creator_name)

            # Record success
            file_size = video_path.stat().st_size
            self.db.record_upload(creator_name, video_path.name, 'completed', profile_id)
            self.db.add_to_history(video_path.name, creator_name, profile_id, page_name, file_size, False)

            logging.info(f"✓ Successfully uploaded: {video_path.name}")

            # Delete video if configured
            if self.config.get('upload_settings.delete_after_upload', False):
                video_path.unlink()
                logging.info(f"Deleted: {video_path.name}")

            # Wait after upload
            wait_time = self.config.get('upload_settings.wait_after_upload', 30)
            time.sleep(wait_time)

        except Exception as e:
            logging.error(f"Upload failed: {e}")
            self.db.record_upload(creator_name, video_path.name, 'failed', profile_id, str(e))
            raise

    def perform_upload(self, driver: webdriver.Chrome, video_path: Path, creator_name: str):
        """
        Perform the actual upload process

        Args:
            driver: Selenium WebDriver
            video_path: Path to video file
            creator_name: Creator name
        """
        # Load metadata
        metadata = self.load_video_metadata(creator_name, video_path.name)

        # Find and click create video button (multiple strategies)
        self.click_create_video_button(driver)

        # Find file input element
        file_input = self.find_file_input(driver)

        if not file_input:
            raise Exception("Could not find file input element")

        # Upload file
        logging.info("Uploading file...")
        file_input.send_keys(str(video_path.absolute()))
        time.sleep(5)

        # Fill in metadata
        self.fill_metadata(driver, metadata)

        # Wait for upload to complete
        self.wait_for_upload_complete(driver)

        # Click publish button
        self.click_publish_button(driver)

        # Wait for confirmation
        time.sleep(10)

        logging.info("Upload process completed")

    def click_create_video_button(self, driver: webdriver.Chrome):
        """
        Click the create video / upload button

        Args:
            driver: Selenium WebDriver
        """
        logging.info("Looking for create video button...")

        # Multiple strategies to find the button
        selectors = [
            "//span[contains(text(), 'Create video')]",
            "//span[contains(text(), 'Upload video')]",
            "//span[contains(text(), 'Add video')]",
            "//div[@aria-label='Create video']",
            "//div[contains(@aria-label, 'upload')]",
            "//button[contains(text(), 'Create')]",
        ]

        for selector in selectors:
            try:
                element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                element.click()
                logging.info("Clicked create video button")
                time.sleep(3)
                return
            except (TimeoutException, NoSuchElementException):
                continue

        # If no button found, we might already be on upload page
        logging.info("No create button found, assuming already on upload page")

    def find_file_input(self, driver: webdriver.Chrome, timeout: int = 30) -> Optional[any]:
        """
        Find file upload input element

        Args:
            driver: Selenium WebDriver
            timeout: Maximum wait time

        Returns:
            File input element or None
        """
        logging.info("Looking for file input...")

        # Common selectors for file input
        selectors = [
            "input[type='file']",
            "input[accept*='video']",
            "input[accept*='mp4']",
            "//input[@type='file']",
        ]

        for selector in selectors:
            try:
                by_type = By.CSS_SELECTOR if not selector.startswith('//') else By.XPATH
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by_type, selector))
                )
                logging.info("Found file input element")
                return element
            except TimeoutException:
                continue

        # Try to make hidden input visible
        try:
            driver.execute_script("""
                var inputs = document.querySelectorAll('input[type=file]');
                for(var i = 0; i < inputs.length; i++) {
                    inputs[i].style.display = 'block';
                    inputs[i].style.visibility = 'visible';
                    inputs[i].style.opacity = '1';
                }
            """)
            time.sleep(2)

            element = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            return element
        except Exception as e:
            logging.error(f"Could not find file input: {e}")
            return None

    def fill_metadata(self, driver: webdriver.Chrome, metadata: Dict):
        """
        Fill in video metadata (title, description, tags)

        Args:
            driver: Selenium WebDriver
            metadata: Metadata dictionary
        """
        logging.info("Filling metadata...")

        # Fill title
        title = metadata.get('title', '')
        if title:
            try:
                # Try different selectors for title field
                title_selectors = [
                    "//label[contains(text(), 'Title')]/following::input[1]",
                    "//input[@placeholder*='Title']",
                    "//textarea[@placeholder*='Title']",
                    "input[aria-label*='Title']",
                    "textarea[aria-label*='Title']",
                ]

                for selector in title_selectors:
                    try:
                        by_type = By.XPATH if selector.startswith('//') else By.CSS_SELECTOR
                        title_field = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((by_type, selector))
                        )
                        title_field.clear()
                        title_field.send_keys(title)
                        logging.info(f"Set title: {title}")
                        break
                    except TimeoutException:
                        continue

            except Exception as e:
                logging.warning(f"Could not set title: {e}")

        # Fill description
        description = metadata.get('description', '')
        if description:
            try:
                # Try different selectors for description field
                desc_selectors = [
                    "//label[contains(text(), 'Description')]/following::textarea[1]",
                    "//textarea[@placeholder*='Description']",
                    "//div[@contenteditable='true']",
                    "textarea[aria-label*='Description']",
                    "div[aria-label*='Description']",
                ]

                for selector in desc_selectors:
                    try:
                        by_type = By.XPATH if selector.startswith('//') else By.CSS_SELECTOR
                        desc_field = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((by_type, selector))
                        )
                        desc_field.clear()
                        desc_field.send_keys(description)
                        logging.info(f"Set description: {description[:50]}...")
                        break
                    except TimeoutException:
                        continue

            except Exception as e:
                logging.warning(f"Could not set description: {e}")

        # Add tags (if supported)
        tags = metadata.get('tags', [])
        if tags:
            logging.info(f"Tags: {', '.join(tags)}")
            # Tags implementation depends on Facebook's UI
            # May need to append to description as #hashtags

    def wait_for_upload_complete(self, driver: webdriver.Chrome):
        """
        Wait for video upload and processing to complete

        Args:
            driver: Selenium WebDriver
        """
        max_wait = self.config.get('upload_settings.upload_timeout', 600)
        start_time = time.time()

        logging.info("Waiting for upload to complete...")

        while time.time() - start_time < max_wait:
            try:
                # Look for progress indicators
                # Method 1: Progress bar
                try:
                    progress = driver.find_element(By.CSS_SELECTOR, "[role='progressbar']")
                    progress_value = progress.get_attribute('aria-valuenow')

                    if progress_value:
                        logging.info(f"Upload progress: {progress_value}%")

                        if int(progress_value) >= 100:
                            logging.info("Upload complete (100%)")
                            time.sleep(5)
                            break
                except NoSuchElementException:
                    pass

                # Method 2: Look for completion message
                try:
                    driver.find_element(By.XPATH, "//*[contains(text(), 'Upload complete')]")
                    logging.info("Upload complete message found")
                    break
                except NoSuchElementException:
                    pass

                # Method 3: Check if publish button is enabled
                try:
                    publish_btn = driver.find_element(By.XPATH, "//span[contains(text(), 'Publish')] | //span[contains(text(), 'Post')]")
                    if publish_btn.is_enabled():
                        logging.info("Publish button enabled")
                        break
                except NoSuchElementException:
                    pass

                time.sleep(5)

            except Exception as e:
                logging.debug(f"Error checking upload status: {e}")
                time.sleep(5)

        if time.time() - start_time >= max_wait:
            logging.warning("Upload timeout reached")

    def click_publish_button(self, driver: webdriver.Chrome):
        """
        Click the publish/post button

        Args:
            driver: Selenium WebDriver
        """
        logging.info("Looking for publish button...")

        # Multiple button text variants
        button_texts = ['Publish', 'Post', 'Share', 'Submit']

        for text in button_texts:
            try:
                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{text}')]/ancestor::button | //button[contains(text(), '{text}')]"))
                )
                button.click()
                logging.info(f"Clicked '{text}' button")
                return
            except TimeoutException:
                continue

        logging.warning("Could not find publish button")

    def needs_login(self, driver: webdriver.Chrome) -> bool:
        """
        Check if login is required

        Args:
            driver: Selenium WebDriver

        Returns:
            True if login needed
        """
        current_url = driver.current_url.lower()
        login_indicators = ['login', 'signin', 'authenticate', 'checkpoint']

        # Check URL
        if any(indicator in current_url for indicator in login_indicators):
            return True

        # Check for login form elements
        try:
            driver.find_element(By.ID, "email")
            driver.find_element(By.ID, "pass")
            return True
        except NoSuchElementException:
            pass

        return False

    def handle_login(self, driver: webdriver.Chrome, creator_data: Dict) -> bool:
        """
        Handle Facebook login

        Args:
            driver: Selenium WebDriver
            creator_data: Creator data including login info

        Returns:
            True if login successful
        """
        logging.info("Handling Facebook login...")

        try:
            # Get login credentials
            email = creator_data.get('facebook_email', '')
            password = creator_data.get('facebook_password', '')

            if not email or not password:
                logging.error("No login credentials provided")
                return False

            # Find and fill email
            try:
                email_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "email"))
                )
                email_field.clear()
                email_field.send_keys(email)
                logging.info("Entered email")
            except TimeoutException:
                logging.error("Could not find email field")
                return False

            # Find and fill password
            try:
                password_field = driver.find_element(By.ID, "pass")
                password_field.clear()
                password_field.send_keys(password)
                logging.info("Entered password")
            except NoSuchElementException:
                logging.error("Could not find password field")
                return False

            # Click login button
            try:
                login_button = driver.find_element(By.NAME, "login")
                login_button.click()
                logging.info("Clicked login button")
            except NoSuchElementException:
                # Try pressing Enter
                password_field.send_keys(Keys.RETURN)
                logging.info("Submitted login form")

            # Wait for login to complete
            wait_time = self.config.get('facebook.wait_for_login', 20)
            time.sleep(wait_time)

            # Check if login successful
            if self.needs_login(driver):
                # Might be 2FA or checkpoint
                logging.warning("Login requires additional verification")
                logging.info("Please complete verification manually...")

                # Wait for manual intervention
                check_interval = self.config.get('facebook.check_login_interval', 2)
                max_wait = 300  # 5 minutes

                for _ in range(max_wait // check_interval):
                    time.sleep(check_interval)
                    if not self.needs_login(driver):
                        logging.info("Login completed")
                        return True

                logging.error("Login timeout - manual verification not completed")
                return False

            logging.info("Login successful")
            return True

        except Exception as e:
            logging.error(f"Login failed: {e}")
            return False

    def get_upload_url(self, page_id: str = '') -> str:
        """
        Get Facebook upload URL

        Args:
            page_id: Facebook page ID (optional)

        Returns:
            Upload URL
        """
        if page_id:
            return self.config.get('facebook.page_upload_url', '').replace('{page_id}', page_id)
        else:
            return self.config.get('facebook.video_upload_url', 'https://www.facebook.com/')

    def load_video_metadata(self, creator_name: str, video_name: str) -> Dict:
        """
        Load metadata for a video from videos_description.json

        Args:
            creator_name: Creator folder name
            video_name: Video filename

        Returns:
            Metadata dictionary
        """
        creators_folder = Path(self.config.get('paths.creators_folder'))
        metadata_file = creators_folder / creator_name / 'videos_description.json'

        if not metadata_file.exists():
            logging.info(f"No metadata file found for {creator_name}")
            return {}

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                all_metadata = json.load(f)

            metadata = all_metadata.get(video_name, {})
            logging.info(f"Loaded metadata for {video_name}")
            return metadata

        except Exception as e:
            logging.error(f"Error loading metadata: {e}")
            return {}
