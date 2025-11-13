"""
Core systems for ixBrowser approach.

This package contains:
- state_manager: Bot state persistence and recovery
- network_monitor: Network health monitoring and reconnection
- folder_queue: Folder queue management and infinite loop
"""

from .state_manager import StateManager
from .network_monitor import NetworkMonitor
from .folder_queue import FolderQueueManager

__all__ = [
    'StateManager',
    'NetworkMonitor',
    'FolderQueueManager',
]
