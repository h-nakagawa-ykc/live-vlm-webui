"""
Frame selection strategies for multi-frame video analysis.
"""

from typing import List

import numpy as np
from PIL import Image


class FrameSelector:
    """Select representative frames using interval and scene-change heuristics."""

    def __init__(self, scene_change_threshold: float = 20.0):
        self.scene_change_threshold = float(scene_change_threshold)

    def select_interval(self, frames: List[Image.Image], step: int) -> List[Image.Image]:
        """Select frames at a fixed interval."""
        if not frames:
            return []
        step = max(1, int(step))
        selected = frames[::step]
        if selected[-1] is not frames[-1]:
            selected.append(frames[-1])
        return selected

    def select_scene_change(self, frames: List[Image.Image]) -> List[Image.Image]:
        """Select frames where average pixel difference crosses threshold."""
        if not frames:
            return []

        selected: List[Image.Image] = [frames[0]]
        prev = np.asarray(frames[0], dtype=np.float32)

        for frame in frames[1:]:
            cur = np.asarray(frame, dtype=np.float32)
            diff_score = float(np.mean(np.abs(cur - prev)))
            if diff_score >= self.scene_change_threshold:
                selected.append(frame)
                prev = cur

        if selected[-1] is not frames[-1]:
            selected.append(frames[-1])

        return selected

    def select_representative(
        self, frames: List[Image.Image], target_count: int, interval_step: int
    ) -> List[Image.Image]:
        """
        Combine interval and scene-change selections and cap to target_count.
        """
        if not frames:
            return []

        target_count = max(1, int(target_count))

        interval_selected = self.select_interval(frames, interval_step)
        scene_selected = self.select_scene_change(frames)

        combined: List[Image.Image] = []
        seen_ids = set()
        for frame in interval_selected + scene_selected:
            frame_id = id(frame)
            if frame_id in seen_ids:
                continue
            seen_ids.add(frame_id)
            combined.append(frame)
            if len(combined) >= target_count:
                break

        return combined if combined else [frames[-1]]
