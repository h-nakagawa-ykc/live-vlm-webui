"""
Frame buffer utilities for multi-frame VLM inference.
"""

from collections import deque
from threading import Lock
from typing import Deque, List

from PIL import Image


class FrameBuffer:
    """Fixed-size frame buffer with thread-safe snapshot and clear operations."""

    def __init__(self, max_size: int = 16):
        self.max_size = max(1, int(max_size))
        self._frames: Deque[Image.Image] = deque(maxlen=self.max_size)
        self._lock = Lock()

    def add(self, frame: Image.Image) -> int:
        """Add a frame and return current size."""
        with self._lock:
            self._frames.append(frame)
            return len(self._frames)

    def snapshot(self) -> List[Image.Image]:
        """Return a copy of buffered frames."""
        with self._lock:
            return list(self._frames)

    def clear(self) -> None:
        """Clear all buffered frames."""
        with self._lock:
            self._frames.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._frames)
