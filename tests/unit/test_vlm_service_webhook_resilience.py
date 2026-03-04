import pytest
from PIL import Image

from live_vlm_webui.vlm_service import VLMService


class _FakeDispatcher:
    class _Config:
        include_metrics = True

    config = _Config()

    async def dispatch(self, _payload, mode="single"):
        raise RuntimeError(f"dispatch failed in {mode}")


@pytest.mark.asyncio
async def test_process_frame_updates_response_even_if_dispatch_fails():
    service = VLMService(
        model="dummy-model",
        api_base="http://localhost:11434/v1",
        api_key="EMPTY",
        prompt="test",
        max_tokens=16,
        event_dispatcher=_FakeDispatcher(),
    )

    async def _fake_analyze(_image, _prompt=None):
        return "inference-ok"

    service.analyze_image = _fake_analyze

    image = Image.new("RGB", (2, 2), color="black")
    await service.process_frame(image)

    assert service.current_response == "inference-ok"
    assert service.is_processing is False
