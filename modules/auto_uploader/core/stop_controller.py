"""
Stop Controller - Global hotkey to stop bot automation
Press Ctrl+X to stop the bot gracefully
"""

import threading
import logging
import sys

logger = logging.getLogger(__name__)

# Global stop flag
_stop_requested = False
_stop_lock = threading.Lock()
_listener_started = False


def is_stop_requested() -> bool:
    """Check if stop has been requested."""
    with _stop_lock:
        return _stop_requested


def request_stop():
    """Request the bot to stop."""
    global _stop_requested
    with _stop_lock:
        _stop_requested = True
    logger.warning("[StopController] STOP REQUESTED - Bot will stop after current operation")
    print("\n" + "=" * 50)
    print("  STOP REQUESTED (Ctrl+X pressed)")
    print("Bot will stop after current operation...")
    print("=" * 50 + "\n")


def reset_stop():
    """Reset the stop flag (call before starting new automation)."""
    global _stop_requested
    with _stop_lock:
        _stop_requested = False
    logger.info("[StopController] Stop flag reset")


def _on_hotkey():
    """Callback when Ctrl+X is pressed."""
    request_stop()


def start_listener():
    """Start the global hotkey listener for Ctrl+X."""
    global _listener_started

    if _listener_started:
        return True

    try:
        import keyboard

        # Register Ctrl+X hotkey
        keyboard.add_hotkey('ctrl+x', _on_hotkey, suppress=False)
        _listener_started = True

        logger.info("[StopController] Hotkey listener started (Ctrl+X to stop)")
        print("Press Ctrl+X anytime to stop the bot")
        return True

    except ImportError:
        logger.warning("[StopController] 'keyboard' library not installed. Ctrl+X stop disabled.")
        logger.warning("[StopController] Install with: pip install keyboard")
        print("Ctrl+X stop feature requires 'keyboard' library")
        print("    Install with: pip install keyboard")
        return False

    except Exception as e:
        logger.error(f"[StopController] Failed to start hotkey listener: {e}")
        return False


def stop_listener():
    """Stop the hotkey listener."""
    global _listener_started

    if not _listener_started:
        return

    try:
        import keyboard
        keyboard.remove_hotkey('ctrl+x')
        _listener_started = False
        logger.info("[StopController] Hotkey listener stopped")
    except:
        pass


def check_stop_and_raise():
    """
    Check if stop was requested and raise StopRequested exception.
    Call this in loops to enable graceful stopping.
    """
    if is_stop_requested():
        raise StopRequested("User requested stop via Ctrl+X")


class StopRequested(Exception):
    """Exception raised when user requests stop via Ctrl+X."""
    pass


class StopController:
    """
    Context manager for stop controller.

    Usage:
        with StopController():
            for item in items:
                check_stop_and_raise()
                process(item)
    """

    def __enter__(self):
        reset_stop()
        start_listener()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        stop_listener()
        if exc_type is StopRequested:
            logger.info("[StopController] Automation stopped by user request")
            return True
        return False


if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    print("Testing Stop Controller - Press Ctrl+X to stop")

    with StopController():
        for i in range(30):
            try:
                check_stop_and_raise()
                print(f"Working... {i+1}/30")
                time.sleep(1)
            except StopRequested:
                print("Stopped by user!")
                break

    print("Test complete!")
