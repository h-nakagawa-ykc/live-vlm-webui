"""
Multi-frame VLM pipeline with OpenAI-compatible multi-image + fallback support.
"""

import asyncio
import base64
import io
import logging
import time
from typing import List, Optional

from PIL import Image

from .frame_buffer import FrameBuffer
from .frame_selector import FrameSelector
from .vlm_service import VLMService

logger = logging.getLogger(__name__)


class VideoVLMPipeline:
    """Buffer frames, pick representative frames, and run multi-frame VLM inference."""

    def __init__(
        self,
        vlm_service: VLMService,
        buffer_size: int = 16,
        trigger_size: int = 4,
        target_frames: int = 4,
        interval_step: int = 1,
        scene_change_threshold: float = 20.0,
    ):
        self.vlm_service = vlm_service
        self.buffer = FrameBuffer(max_size=buffer_size)
        self.selector = FrameSelector(scene_change_threshold=scene_change_threshold)
        self.trigger_size = max(1, int(trigger_size))
        self.target_frames = max(1, int(target_frames))
        self.interval_step = max(1, int(interval_step))
        self._lock = asyncio.Lock()

    async def process_frame(self, image: Image.Image, prompt: Optional[str] = None) -> None:
        """Collect one frame and trigger inference when enough frames are available."""
        current_size = self.buffer.add(image)
        if current_size < self.trigger_size:
            return

        if self._lock.locked():
            logger.debug("Pipeline is busy, buffering frame only")
            return

        async with self._lock:
            frames = self.buffer.snapshot()
            self.buffer.clear()
            if not frames:
                return

            selected = self.selector.select_representative(
                frames=frames, target_count=self.target_frames, interval_step=self.interval_step
            )
            if not selected:
                return

            self.vlm_service.is_processing = True
            try:
                if len(selected) == 1:
                    result = await self.vlm_service.analyze_image(selected[0], prompt=prompt)
                else:
                    result = await self._analyze_multi_with_fallback(selected, prompt=prompt)
                self.vlm_service.current_response = result
            except Exception as e:
                logger.error(f"VideoVLMPipeline inference failed: {e}", exc_info=True)
                self.vlm_service.current_response = f"Error: {str(e)}"
            finally:
                self.vlm_service.is_processing = False

    async def _analyze_multi_with_fallback(
        self, frames: List[Image.Image], prompt: Optional[str] = None
    ) -> str:
        """Try multi-image request first; if unsupported, fallback to per-frame inference."""
        try:
            return await self._analyze_multi_image(frames, prompt=prompt)
        except Exception as e:
            logger.warning(
                f"Multi-image inference failed, using single-image fallback: {e}",
                exc_info=True,
            )
            results = []
            for i, frame in enumerate(frames, start=1):
                frame_prompt = prompt or self.vlm_service.prompt
                frame_prompt = f"{frame_prompt}\n\nFrame {i}/{len(frames)}"
                result = await self.vlm_service.analyze_image(frame, prompt=frame_prompt)
                results.append(f"[Frame {i}] {result}")
            return "\n".join(results)

    async def _analyze_multi_image(self, frames: List[Image.Image], prompt: Optional[str] = None) -> str:
        """Call OpenAI-compatible chat completion with multiple image_url entries."""
        prompt_text = prompt or self.vlm_service.prompt

        content = [{"type": "text", "text": prompt_text}]
        for frame in frames:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{self._to_base64(frame)}"},
                }
            )

        messages = [{"role": "user", "content": content}]

        start_time = time.perf_counter()
        response = await self.vlm_service.client.chat.completions.create(
            model=self.vlm_service.model,
            messages=messages,
            max_tokens=self.vlm_service.max_tokens,
            temperature=0.7,
        )
        elapsed = time.perf_counter() - start_time

        self.vlm_service.last_inference_time = elapsed
        self.vlm_service.total_inferences += 1
        self.vlm_service.total_inference_time += elapsed

        result = (response.choices[0].message.content or "").strip()
        logger.info(
            f"Multi-frame VLM response generated from {len(frames)} frames "
            f"(latency: {elapsed*1000:.0f}ms)"
        )
        return result

    @staticmethod
    def _to_base64(image: Image.Image) -> str:
        """Convert PIL image to base64-encoded JPEG."""
        buff = io.BytesIO()
        image.save(buff, format="JPEG")
        return base64.b64encode(buff.getvalue()).decode("utf-8")
