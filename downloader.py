import os
from PyQt5.QtCore import QThread, pyqtSignal
import yt_dlp


class DownloadThread(QThread):
    """Background thread for downloading videos without blocking UI"""
    
    # Signals to communicate with GUI
    progress = pyqtSignal(str)  # Status messages
    progress_percent = pyqtSignal(int)  # Progress percentage
    finished = pyqtSignal(bool, str)  # Success/failure with message
    
    def __init__(self, url, save_path, options):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.options = options
        self.is_cancelled = False
    
    def progress_hook(self, d):
        """Called by yt-dlp during download to report progress"""
        if self.is_cancelled:
            raise Exception("Download cancelled by user")
        
        if d['status'] == 'downloading':
            try:
                # Extract progress information
                percent_str = d.get('_percent_str', '0%').strip('%')
                percent = float(percent_str)
                self.progress_percent.emit(int(percent))
                
                # Get download details
                downloaded = d.get('_downloaded_bytes_str', 'N/A')
                total = d.get('_total_bytes_str', 'N/A')
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                
                msg = f"📥 {downloaded}/{total} | Speed: {speed} | ETA: {eta}"
                self.progress.emit(msg)
            except Exception as e:
                self.progress.emit("Downloading...")
                
        elif d['status'] == 'finished':
            self.progress.emit("✓ Download complete, processing file...")
    
    def run(self):
        """Main download execution"""
        try:
            # Configure yt-dlp options
            ydl_opts = {
                'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),
                'progress_hooks': [self.progress_hook],
                'quiet': False,
                'no_warnings': False,
            }
            
            # Set video quality
            quality = self.options.get('quality', 'best')
            if quality == 'Best':
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            elif quality == 'Medium':
                ydl_opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best'
            elif quality == 'Low':
                ydl_opts['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best'
            
            # Video post-processing
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
            
            # Handle playlists
            if self.options.get('playlist', False):
                ydl_opts['noplaylist'] = False
                self.progress.emit("🎵 Playlist mode enabled - downloading all videos...")
            else:
                ydl_opts['noplaylist'] = True
            
            # Subtitle options
            if self.options.get('subtitles', False):
                ydl_opts['writesubtitles'] = True
                ydl_opts['writeautomaticsub'] = True
                self.progress.emit("📝 Subtitles will be downloaded")
            
            # Thumbnail options
            if self.options.get('thumbnail', False):
                ydl_opts['writethumbnail'] = True
                self.progress.emit("🖼️ Thumbnail will be saved")
            
            # Start download
            self.progress.emit("🚀 Initializing download...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info and download
                info = ydl.extract_info(self.url, download=True)
                
                # Get video title
                if 'entries' in info:  # Playlist
                    video_count = len(info['entries'])
                    title = f"{video_count} videos from playlist"
                else:  # Single video
                    title = info.get('title', 'Unknown')
                
                self.finished.emit(True, f"✅ Successfully downloaded: {title}")
            
        except Exception as e:
            error_msg = str(e)
            if "cancelled" in error_msg.lower():
                self.finished.emit(False, "⚠️ Download cancelled")
            else:
                self.finished.emit(False, f"❌ Error: {error_msg}")
    
    def cancel(self):
        """Cancel ongoing download"""
        self.is_cancelled = True
