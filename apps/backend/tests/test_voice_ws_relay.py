"""Regression tests for the Vobiz playback relay's burst handling."""

import asyncio
import json
from collections import deque

import pytest
from starlette.websockets import WebSocketState

from app.api import voice_ws
from app.api.voice_ws import (
    PLAY_CHUNK_BYTES,
    PlaybackState,
    _relay_agent_audio,
)
from app.services.agent.bridge import BridgeEvent


class FakeWebSocket:
    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.application_state = WebSocketState.CONNECTED
        self.sent: list[str] = []

    async def send_text(self, payload: str) -> None:
        self.sent.append(payload)


class ScriptedBridge:
    """Yields audio events faster than the sender drains them."""

    def __init__(self, events: list[BridgeEvent]) -> None:
        self._events: deque[BridgeEvent] = deque(events)

    async def receive_event(self, call_id: str) -> BridgeEvent:
        if self._events:
            await asyncio.sleep(0)  # Yield like a real network receive does.
            return self._events.popleft()
        return BridgeEvent("closed")


@pytest.fixture()
def large_audio_events() -> list[BridgeEvent]:
    # Each event is ~1 second of audio (16 kB) -> ~34 chunks of 480 bytes.
    # Enough events to exceed the queue limit many times over.
    return [BridgeEvent("audio", b"\xff" * (PLAY_CHUNK_BYTES * 34)) for _ in range(200)]


async def _run_relay(events: list[BridgeEvent], monkeypatch) -> tuple[FakeWebSocket, PlaybackState]:
    monkeypatch.setattr(voice_ws, "PLAY_SEND_INTERVAL_SECONDS", 0)
    websocket = FakeWebSocket()
    playback = PlaybackState()
    bridge = ScriptedBridge(events)
    await _relay_agent_audio(websocket, bridge, "call_test", "stream_test", playback)
    return websocket, playback


def _event(payload: str) -> dict:
    return json.loads(payload)


def test_relay_survives_tts_burst_and_keeps_sending_audio(large_audio_events, monkeypatch):
    websocket, _ = asyncio.run(_run_relay(large_audio_events, monkeypatch))

    stops = [frame for frame in websocket.sent if _event(frame).get("event") == "stop"]
    plays = [frame for frame in websocket.sent if _event(frame).get("event") == "playAudio"]

    # The burst outran the sender, but the relay never stopped the stream:
    # it kept sending audio through the whole burst and only stopped once
    # ElevenLabs closed. (Old behavior: first QueueFull cleared the queue,
    # sent stop, and returned — killing all audio mid-call.)
    assert len(plays) > 100
    assert len(stops) == 1
    assert websocket.sent[-1] == stops[0]


def test_relay_forwards_interruption_clear(large_audio_events, monkeypatch):
    events = large_audio_events[:5]
    events.insert(2, BridgeEvent("interruption"))
    websocket, _ = asyncio.run(_run_relay(events, monkeypatch))

    clears = [frame for frame in websocket.sent if _event(frame).get("event") == "clearAudio"]
    assert len(clears) == 1
