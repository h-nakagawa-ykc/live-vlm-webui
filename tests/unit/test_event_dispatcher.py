import pytest

from live_vlm_webui.event_dispatcher import EventDispatcher, EventDispatcherConfig


class _RaisingSession:
    closed = False

    def post(self, *_args, **_kwargs):
        raise RuntimeError("connection refused")


@pytest.mark.asyncio
async def test_dispatch_returns_false_on_connection_error():
    dispatcher = EventDispatcher(
        EventDispatcherConfig(
            enabled=True,
            url="http://127.0.0.1:9/events",
            timeout_sec=0.5,
            mode="both",
            sample_every=1,
            include_metrics=True,
        ),
        session=_RaisingSession(),
    )

    ok = await dispatcher.dispatch({"text": "hello"}, mode="single")

    assert ok is False
