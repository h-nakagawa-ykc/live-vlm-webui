# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
VLM Service
Handles async image analysis using any OpenAI-compatible VLM API
(Works with vLLM, SGLang, Ollama, OpenAI, etc.)
"""

import asyncio
import base64
import hashlib
import io
import json
import time
from openai import AsyncOpenAI
from PIL import Image
from typing import Optional, Any
import logging

from .event_dispatcher import EventDispatcher

logger = logging.getLogger(__name__)


class VLMService:
    """Service for analyzing images using VLM via OpenAI-compatible API"""

    def __init__(
        self,
        model: str,
        api_base: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        prompt: str = "Describe what you see in this image in one sentence.",
        max_tokens: int = 512,
        event_dispatcher: Optional[EventDispatcher] = None,
        camera_id: str = "",
        stream_id: str = "",
        inference_prompt_id: Optional[str] = None,
    ):
        """
        Initialize VLM service

        Args:
            model: Model name (e.g., "llama-3.2-11b-vision-instruct" for vLLM)
            api_base: Base URL for the API (e.g., "http://localhost:8000/v1" for vLLM)
            api_key: API key (use "EMPTY" for local servers)
            prompt: Default prompt to use for image analysis
            max_tokens: Maximum tokens to generate
        """
        self.model = model
        self.api_base = api_base
        self.api_key = api_key if api_key else "EMPTY"
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.client = AsyncOpenAI(base_url=api_base, api_key=api_key)
        self.event_dispatcher = event_dispatcher
        self.current_response = "Initializing..."
        self.is_processing = False
        self._processing_lock = asyncio.Lock()
        self.camera_id = camera_id.strip()
        self.stream_id = stream_id.strip()
        self.inference_prompt_id = (
            inference_prompt_id.strip()
            if inference_prompt_id and inference_prompt_id.strip()
            else self._derive_prompt_id(self.prompt)
        )

        # Metrics tracking
        self.last_inference_time = 0.0  # seconds
        self.total_inferences = 0
        self.total_inference_time = 0.0

    async def analyze_image(self, image: Image.Image, prompt: Optional[str] = None) -> str:
        """
        Analyze an image using the VLM model

        Args:
            image: PIL Image to analyze
            prompt: Prompt for the VLM (uses default if None)

        Returns:
            Generated response string
        """
        if prompt is None:
            prompt = self.prompt

        try:
            start_time = time.perf_counter()

            # Convert PIL Image to base64
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format="JPEG")
            img_byte_arr = img_byte_arr.getvalue()
            img_base64 = base64.b64encode(img_byte_arr).decode("utf-8")

            # Create message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                        },
                    ],
                }
            ]

            # Call API
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=self.max_tokens, temperature=0.7
            )

            # Calculate latency
            end_time = time.perf_counter()
            inference_time = end_time - start_time

            # Update metrics
            self.last_inference_time = inference_time
            self.total_inferences += 1
            self.total_inference_time += inference_time

            result = response.choices[0].message.content.strip()
            logger.info(f"VLM response: {result} (latency: {inference_time*1000:.0f}ms)")
            return result

        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return f"Error: {str(e)}"

    async def process_frame(self, image: Image.Image, prompt: Optional[str] = None) -> None:
        """
        Process a frame asynchronously. Updates self.current_response when done.
        If already processing, this call is skipped.

        Args:
            image: PIL Image to process
            prompt: Optional custom prompt (uses default if None)
        """
        # Non-blocking check if we're already processing
        if self._processing_lock.locked():
            logger.debug("VLM busy, skipping frame")
            return

        async with self._processing_lock:
            self.is_processing = True
            try:
                response = await self.analyze_image(image, prompt)
                self.current_response = response
                await self._dispatch_single_inference_event(response)
            finally:
                self.is_processing = False

    async def _dispatch_single_inference_event(self, response: str) -> None:
        """
        Dispatch single-frame inference event if dispatcher is configured.
        Failures are intentionally non-fatal.
        """
        if not self.event_dispatcher:
            return

        payload = self.build_webhook_payload(response=response, mode="single")
        if self.event_dispatcher.config.include_metrics:
            payload["metrics"] = self.get_metrics()

        try:
            await self.event_dispatcher.dispatch(payload, mode="single")
        except Exception as e:
            logger.error("Unexpected webhook dispatch error in single mode: %s", e)

    def get_current_response(self) -> tuple[str, bool]:
        """
        Get the current response and processing status

        Returns:
            Tuple of (response, is_processing)
        """
        return self.current_response, self.is_processing

    def get_metrics(self) -> dict:
        """
        Get current performance metrics

        Returns:
            Dict with latency and throughput metrics
        """
        avg_latency = (
            self.total_inference_time / self.total_inferences if self.total_inferences > 0 else 0.0
        )

        return {
            "last_latency_ms": self.last_inference_time * 1000,
            "avg_latency_ms": avg_latency * 1000,
            "total_inferences": self.total_inferences,
            "is_processing": self.is_processing,
        }

    def update_prompt(self, new_prompt: str, max_tokens: Optional[int] = None) -> None:
        """
        Update the default prompt and optionally max_tokens

        Args:
            new_prompt: New prompt to use
            max_tokens: Maximum tokens to generate (optional)
        """
        self.prompt = new_prompt
        self.inference_prompt_id = self._derive_prompt_id(new_prompt)
        if max_tokens is not None:
            self.max_tokens = max_tokens
            logger.info(f"Updated prompt to: {new_prompt}, max_tokens: {max_tokens}")
        else:
            logger.info(f"Updated prompt to: {new_prompt}")

    def set_stream_context(
        self, stream_id: Optional[str] = None, camera_id: Optional[str] = None
    ) -> None:
        """Update optional source context for webhook payload enrichment."""
        if stream_id is not None:
            self.stream_id = str(stream_id).strip()
        if camera_id is not None:
            self.camera_id = str(camera_id).strip()

    def update_api_settings(
        self, api_base: Optional[str] = None, api_key: Optional[str] = None
    ) -> None:
        """
        Update API base URL and/or API key, recreating the client

        Args:
            api_base: New API base URL (optional)
            api_key: New API key (optional, use empty string for local services)
        """
        if api_base:
            self.api_base = api_base
        if api_key is not None:  # Allow empty string
            self.api_key = api_key if api_key else "EMPTY"

        # Recreate the client with new settings
        self.client = AsyncOpenAI(base_url=self.api_base, api_key=self.api_key)

        masked_key = (
            "***" + self.api_key[-4:]
            if self.api_key and len(self.api_key) > 4 and self.api_key != "EMPTY"
            else "EMPTY"
        )
        logger.info(f"Updated API settings - base: {self.api_base}, key: {masked_key}")

    def build_webhook_payload(
        self, response: str, mode: str, extra_fields: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Build v1.1-compatible webhook payload while preserving backward compatibility.
        New fields are optional and only populated when values are available.
        """
        payload: dict[str, Any] = {
            "mode": mode,
            "text": response,
            "model": self.model,
            "api_base": self.api_base,
        }

        parsed = self._extract_structured_fields(response)
        if parsed["risk_score"] is not None:
            payload["risk_score"] = parsed["risk_score"]
        if parsed["labels"]:
            payload["labels"] = parsed["labels"]

        if self.camera_id:
            payload["camera_id"] = self.camera_id
        if self.stream_id:
            payload["stream_id"] = self.stream_id
        if self.inference_prompt_id:
            payload["inference_prompt_id"] = self.inference_prompt_id

        if extra_fields:
            payload.update(extra_fields)
        return payload

    @staticmethod
    def _derive_prompt_id(prompt: str) -> str:
        digest = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()[:16]
        return f"sha256:{digest}"

    @staticmethod
    def _extract_structured_fields(response: str) -> dict[str, Any]:
        """
        Extract optional structured fields from JSON-like VLM output.
        Expected keys:
        - risk_score: float in [0.0, 1.0]
        - labels: array of strings
        """
        if not response:
            return {"risk_score": None, "labels": []}

        text = response.strip()
        if not text.startswith("{"):
            return {"risk_score": None, "labels": []}

        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return {"risk_score": None, "labels": []}
        if not isinstance(obj, dict):
            return {"risk_score": None, "labels": []}

        risk_score = None
        risk_raw = obj.get("risk_score")
        if risk_raw is not None:
            try:
                risk_val = float(risk_raw)
                if 0.0 <= risk_val <= 1.0:
                    risk_score = risk_val
            except (TypeError, ValueError):
                risk_score = None

        labels: list[str] = []
        labels_raw = obj.get("labels")
        if isinstance(labels_raw, list):
            labels = [str(v) for v in labels_raw if isinstance(v, str) and v.strip()]

        return {"risk_score": risk_score, "labels": labels}
