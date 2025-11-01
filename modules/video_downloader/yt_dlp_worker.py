from typing import Callable, Optional
import os
import threading
import traceback
import yt_dlp

class DownloadCancelled(Exception):
    pass

class YtDlpWorker:
    """Single download worker that uses yt_dlp.YoutubeDL and a progress hook.

    Emits progress via callbacks provided by the caller. Callbacks must be thread-safe
    or should emit Qt signals (preferred) to update the UI from the main thread.
    """
    def __init__(self, url: str, output_dir: str, options: dict, on_progress: Callable, on_complete: Callable, cancel_event: Optional[threading.Event] = None):
        self.url = url
        self.output_dir = output_dir
        self.options = options or {}
        self.on_progress = on_progress  # Callable(url, progress_dict)
        self.on_complete = on_complete  # Callable(success: bool, message: str)
        self.cancel_event = cancel_event or threading.Event()
        self._ydl = None

    def _progress_hook(self, d):
        # d is dict from yt_dlp (status, downloaded_bytes, total_bytes, speed, eta, filename, status)
        try:
            # Check cancel flag and abort cooperatively
            if self.cancel_event.is_set():
                raise DownloadCancelled("User cancelled")
            if self.on_progress:
                try:
                    self.on_progress(self.url, d)
                except Exception:
                    # swallow user callback exceptions to avoid crashing the hook
                    traceback.print_exc()
        except DownloadCancelled:
            # Raising an Exception inside the hook will abort yt_dlp.download
            raise
        except Exception:
            traceback.print_exc()

    def _build_opts(self):
        format_str = self.options.get('format') or 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
        cookiefile = self.options.get('cookiefile')
        outtmpl = os.path.join(self.output_dir, '%(title)s-%(id)s.%(ext)s')
        ydl_opts = {
            'format': format_str,
            'outtmpl': outtmpl,
            'noprogress': True,   # we use hooks
            'progress_hooks': [self._progress_hook],
            'quiet': True,
            'ignoreerrors': False,
            'no_warnings': True,
            'continuedl': True,   # allow resume
            'retries': self.options.get('retries', 3),
        }
        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile
        # subtitles & playlist control
        if self.options.get('subtitles'):
            ydl_opts.update({'writesubtitles': True, 'subtitlesformat': 'srv,vtt'})
        if not self.options.get('playlist', False):
            ydl_opts['noplaylist'] = True
        return ydl_opts

    def run(self):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            ydl_opts = self._build_opts()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._ydl = ydl
                ydl.download([self.url])
            if self.on_complete:
                self.on_complete(True, f"Saved: {self.url}")
        except DownloadCancelled:
            if self.on_complete:
                self.on_complete(False, f"Cancelled: {self.url}")
        except Exception as e:
            if self.on_complete:
                self.on_complete(False, f"Error: {str(e)[:200]}")
