#!/usr/bin/env python3
"""
Test script for Enhanced Link Grabber
Demonstrates the new page inspection capabilities
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.link_grabber.core import LinkGrabberThread
from PyQt5.QtCore import QCoreApplication

def test_youtube_page_inspection():
    """Test YouTube page inspection"""
    print("🧪 Testing YouTube Page Inspection...")
    
    # Test with a popular YouTube channel
    test_url = "https://www.youtube.com/@MrBeast"
    options = {'max_videos': 10}
    
    app = QCoreApplication(sys.argv)
    
    def on_progress(message):
        print(f"📊 Progress: {message}")
    
    def on_progress_percent(percent):
        print(f"📈 Progress: {percent}%")
    
    def on_link_found(url, title):
        print(f"🔗 Found: {title} - {url}")
    
    def on_finished(success, message, links):
        print(f"✅ Finished: {message}")
        print(f"📊 Total links found: {len(links)}")
        app.quit()
    
    grabber = LinkGrabberThread(test_url, options)
    grabber.progress.connect(on_progress)
    grabber.progress_percent.connect(on_progress_percent)
    grabber.link_found.connect(on_link_found)
    grabber.finished.connect(on_finished)
    
    grabber.start()
    app.exec_()

def test_instagram_page_inspection():
    """Test Instagram page inspection"""
    print("\n🧪 Testing Instagram Page Inspection...")
    
    # Test with a public Instagram profile
    test_url = "https://www.instagram.com/cristiano/"
    options = {'max_videos': 5}
    
    app = QCoreApplication(sys.argv)
    
    def on_progress(message):
        print(f"📊 Progress: {message}")
    
    def on_progress_percent(percent):
        print(f"📈 Progress: {percent}%")
    
    def on_link_found(url, title):
        print(f"🔗 Found: {title} - {url}")
    
    def on_finished(success, message, links):
        print(f"✅ Finished: {message}")
        print(f"📊 Total links found: {len(links)}")
        app.quit()
    
    grabber = LinkGrabberThread(test_url, options)
    grabber.progress.connect(on_progress)
    grabber.progress_percent.connect(on_progress_percent)
    grabber.link_found.connect(on_link_found)
    grabber.finished.connect(on_finished)
    
    grabber.start()
    app.exec_()

def test_tiktok_page_inspection():
    """Test TikTok page inspection"""
    print("\n🧪 Testing TikTok Page Inspection...")
    
    # Test with a popular TikTok user
    test_url = "https://www.tiktok.com/@charlidamelio"
    options = {'max_videos': 5}
    
    app = QCoreApplication(sys.argv)
    
    def on_progress(message):
        print(f"📊 Progress: {message}")
    
    def on_progress_percent(percent):
        print(f"📈 Progress: {percent}%")
    
    def on_link_found(url, title):
        print(f"🔗 Found: {title} - {url}")
    
    def on_finished(success, message, links):
        print(f"✅ Finished: {message}")
        print(f"📊 Total links found: {len(links)}")
        app.quit()
    
    grabber = LinkGrabberThread(test_url, options)
    grabber.progress.connect(on_progress)
    grabber.progress_percent.connect(on_progress_percent)
    grabber.link_found.connect(on_link_found)
    grabber.finished.connect(on_finished)
    
    grabber.start()
    app.exec_()

def test_facebook_page_inspection():
    """Test Facebook page inspection"""
    print("\n🧪 Testing Facebook Page Inspection...")
    
    # Test with a public Facebook page
    test_url = "https://www.facebook.com/NASA"
    options = {'max_videos': 5}
    
    app = QCoreApplication(sys.argv)
    
    def on_progress(message):
        print(f"📊 Progress: {message}")
    
    def on_progress_percent(percent):
        print(f"📈 Progress: {percent}%")
    
    def on_link_found(url, title):
        print(f"🔗 Found: {title} - {url}")
    
    def on_finished(success, message, links):
        print(f"✅ Finished: {message}")
        print(f"📊 Total links found: {len(links)}")
        app.quit()
    
    grabber = LinkGrabberThread(test_url, options)
    grabber.progress.connect(on_progress)
    grabber.progress_percent.connect(on_progress_percent)
    grabber.link_found.connect(on_link_found)
    grabber.finished.connect(on_finished)
    
    grabber.start()
    app.exec_()

if __name__ == "__main__":
    print("🚀 Enhanced Link Grabber Test Suite")
    print("=" * 50)
    
    # Test each platform
    try:
        test_youtube_page_inspection()
    except Exception as e:
        print(f"❌ YouTube test failed: {e}")
    
    try:
        test_instagram_page_inspection()
    except Exception as e:
        print(f"❌ Instagram test failed: {e}")
    
    try:
        test_tiktok_page_inspection()
    except Exception as e:
        print(f"❌ TikTok test failed: {e}")
    
    try:
        test_facebook_page_inspection()
    except Exception as e:
        print(f"❌ Facebook test failed: {e}")
    
    print("\n🎉 Test suite completed!")
