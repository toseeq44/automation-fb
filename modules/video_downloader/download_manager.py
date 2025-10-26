import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Callable, List
from .yt_dlp_worker import YtDlpWorker
import time

class DownloadManager:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._folder_locks: Dict[str, threading.Lock] = {}
        self._global_cancel = threading.Event()
        self._tasks = []  # keep track of (future, cancel_event, task_meta)

    def _get_folder_lock(self, folder: str) -> threading.Lock:
        folder = str(Path(folder).resolve())
        if folder not in self._folder_locks:
            self._folder_locks[folder] = threading.Lock()
        return self._folder_locks[folder]

    def submit_many(self, tasks: List[dict], on_progress: Callable, on_complete: Callable):
        """
        tasks: list of dicts with keys: url, folder, options
        on_progress(url, progress_dict) -> called by worker hook
        on_complete(success, message, task_meta) -> called when each task ends
        """
        for t in tasks:
            ev = threading.Event()
            # Worker will check ev; we also check global cancel
            combined_event = threading.Event()
            # small helper to link events: if global cancel set, set combined
            def watch(local_ev=ev, combined=combined_event):
                while not (local_ev.is_set() or self._global_cancel.is_set()):
                    time.sleep(0.1)
                combined.set()
            threading.Thread(target=watch, daemon=True).start()

            options = t.get('options', {})
            worker = YtDlpWorker(t['url'], t['folder'], options, on_progress, lambda s, m, _t=t: self._on_complete(_t, s, m, on_complete), cancel_event=combined_event)
            future = self.executor.submit(worker.run)
            self._tasks.append((future, ev, t))
        return self._tasks

    def _on_complete(self, task, success, message, on_complete):
        # Called from worker thread; ensure we update downloaded_links atomically
        folder = task['folder']
        dl_file = Path(folder) / ".downloaded_links.txt"
        try:
            lock = self._get_folder_lock(folder)
            with lock:
                dl_file.parent.mkdir(parents=True, exist_ok=True)
                with open(dl_file, 'a', encoding='utf-8') as f:
                    f.write(task['url'] + '\n')
        except Exception:
            pass
        if on_complete:
            on_complete(success, message, task)

    def cancel_all(self):
        self._global_cancel.set()
        # set individual events for best effort
        for fut, ev, t in list(self._tasks):
            try:
                ev.set()
            except Exception:
                pass

    def cancel_task(self, task_url: str):
        for fut, ev, t in list(self._tasks):
            if t['url'] == task_url:
                ev.set()
                break
