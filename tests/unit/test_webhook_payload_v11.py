import pytest
from PIL import Image

from live_vlm_webui.video_vlm_pipeline import VideoVLMPipeline
from live_vlm_webui.vlm_service import VLMService


class _CollectorDispatcher:
    class _Config:
        include_metrics = False

    config = _Config()

    def __init__(self):
        self.calls = []

    async def dispatch(self, payload, mode="single"):
        self.calls.append((payload, mode))
        return True


@pytest.mark.asyncio
async def test_single_payload_includes_v11_fields_when_json_response_is_valid():
    dispatcher = _CollectorDispatcher()
    service = VLMService(
        model="dummy-model",
        api_base="http://localhost:11434/v1",
        api_key="EMPTY",
        prompt="detect danger",
        max_tokens=16,
        event_dispatcher=dispatcher,
        camera_id="cam-01",
        stream_id="stream-01",
    )

    async def _fake_analyze(_image, _prompt=None):
        return '{"answer":"yes","risk_score":0.88,"labels":["person","smoke"]}'

    service.analyze_image = _fake_analyze

    image = Image.new("RGB", (2, 2), color="black")
    await service.process_frame(image)

    assert len(dispatcher.calls) == 1
    payload, mode = dispatcher.calls[0]
    assert mode == "single"
    assert payload["mode"] == "single"
    assert payload["risk_score"] == 0.88
    assert payload["labels"] == ["person", "smoke"]
    assert payload["camera_id"] == "cam-01"
    assert payload["stream_id"] == "stream-01"
    assert payload["inference_prompt_id"].startswith("sha256:")


@pytest.mark.asyncio
async def test_multi_payload_includes_v11_fields_and_multi_fields():
    dispatcher = _CollectorDispatcher()
    service = VLMService(
        model="dummy-model",
        api_base="http://localhost:11434/v1",
        api_key="EMPTY",
        prompt="monitor area",
        max_tokens=16,
        event_dispatcher=dispatcher,
        camera_id="cam-yard",
        stream_id="session-yard",
    )
    pipeline = VideoVLMPipeline(
        vlm_service=service,
        buffer_size=4,
        trigger_size=1,
        target_frames=1,
        interval_step=1,
        scene_change_threshold=20.0,
    )

    async def _fake_analyze(_image, prompt=None):
        return '{"risk_score":0.91,"labels":["intrusion"]}'

    service.analyze_image = _fake_analyze

    image = Image.new("RGB", (2, 2), color="white")
    await pipeline.process_frame(image)

    assert len(dispatcher.calls) == 1
    payload, mode = dispatcher.calls[0]
    assert mode == "multi"
    assert payload["mode"] == "multi"
    assert payload["risk_score"] == 0.91
    assert payload["labels"] == ["intrusion"]
    assert payload["camera_id"] == "cam-yard"
    assert payload["stream_id"] == "session-yard"
    assert payload["selected_frame_count"] == 1
    assert payload["buffered_frame_count"] == 1
    assert payload["used_fallback"] is False


def test_prompt_update_changes_inference_prompt_id():
    service = VLMService(
        model="dummy-model",
        api_base="http://localhost:11434/v1",
        api_key="EMPTY",
        prompt="first prompt",
        max_tokens=16,
        event_dispatcher=None,
    )
    first_id = service.inference_prompt_id

    service.update_prompt("second prompt")

    assert service.inference_prompt_id.startswith("sha256:")
    assert service.inference_prompt_id != first_id
