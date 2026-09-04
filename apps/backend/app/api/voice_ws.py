"""Low-latency Vobiz media WebSocket backed by ElevenLabs."""

import asyncio
import base64
import binascii
import json
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hmac import compare_digest
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models.call_attempt import CallAttempt
from app.services.calls.vobiz import callback_signature

router = APIRouter(tags=["voice"])
logger = logging.getLogger(__name__)

OUT_CONTENT_TYPE = "audio/x-mulaw"
OUT_SAMPLE_RATE = 8000
PLAY_CHUNK_BYTES = 480  # 60 ms of μ-law/8 kHz audio.
PLAY_SEND_INTERVAL_SECONDS = 0.04  # Stay ahead of playback without flooding TCP.
PLAYBACK_QUEUE_LIMIT = 256
BARGE_IN_RMS_THRESHOLD = 900
BARGE_IN_TRIGGER_FRAMES = 4  # 80 ms at Vobiz's 20 ms frame cadence.


@dataclass(slots=True)
class PlaybackState:
    """Coordinate the independent ElevenLabs receiver and Vobiz sender."""

    queue: asyncio.Queue[str] = field(
        default_factory=lambda: asyncio.Queue(maxsize=PLAYBACK_QUEUE_LIMIT)
    )
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active_until: float = 0.0
    suppress_agent_audio: bool = False
    barge_in_frames: int = 0
    barge_in_latched: bool = False
    socket_closed: bool = False

    def is_active(self) -> bool:
        return (
            not self.queue.empty()
            or asyncio.get_running_loop().time() < self.active_until
        )

    def enqueue_audio(self, stream_id: str, audio: bytes) -> None:
        if self.suppress_agent_audio or not audio:
            return
        duration = len(audio) / OUT_SAMPLE_RATE
        now = asyncio.get_running_loop().time()
        self.active_until = max(now, self.active_until) + duration
        for offset in range(0, len(audio), PLAY_CHUNK_BYTES):
            chunk = audio[offset : offset + PLAY_CHUNK_BYTES]
            self.queue.put_nowait(_play_message(stream_id, chunk))

    def clear(self) -> None:
        while True:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.active_until = asyncio.get_running_loop().time()
        self.barge_in_frames = 0


def _load_bridge(call_id: str, settings: Settings) -> Any | None:
    """Load the configured bridge without hiding import/configuration failures."""
    try:
        from app.services.agent.bridge import get_bridge

        return get_bridge(settings)
    except Exception:
        logger.exception("Could not initialize the voice bridge for call %s", call_id)
        return None


def _format_label(media_format: dict[str, Any] | None) -> str:
    """Map Vobiz start.mediaFormat into a bridge input label."""
    encoding = str((media_format or {}).get("encoding", "")).lower()
    try:
        rate = int((media_format or {}).get("sampleRate", 8000))
    except (TypeError, ValueError):
        rate = 8000
    if "mulaw" in encoding or "mu-law" in encoding or "ulaw" in encoding:
        return "mulaw-8k-mono"
    if "l16" in encoding or "pcm" in encoding:
        return f"pcm16-{16 if rate == 16000 else 8}k-mono"
    return "mulaw-8k-mono"


def _play_message(stream_id: str, audio: bytes) -> str:
    return json.dumps(
        {
            "event": "playAudio",
            "streamId": stream_id,
            "media": {
                "contentType": OUT_CONTENT_TYPE,
                "sampleRate": OUT_SAMPLE_RATE,
                "payload": base64.b64encode(audio).decode("ascii"),
            },
        }
    )


async def _send_text(
    websocket: WebSocket,
    payload: str,
    playback: PlaybackState,
) -> bool:
    if playback.socket_closed:
        return False
    if (
        websocket.client_state is not WebSocketState.CONNECTED
        or websocket.application_state is not WebSocketState.CONNECTED
    ):
        playback.socket_closed = True
        return False
    async with playback.send_lock:
        if playback.socket_closed:
            return False
        try:
            await websocket.send_text(payload)
            return True
        except (WebSocketDisconnect, RuntimeError):
            playback.socket_closed = True
            return False
        except Exception as error:  # noqa: BLE001 - external socket boundary
            playback.socket_closed = True
            logger.warning(
                "Vobiz socket send failed (%s)",
                type(error).__name__,
            )
            return False


async def _stop_vobiz_stream(
    websocket: WebSocket,
    stream_id: str,
    playback: PlaybackState,
) -> None:
    await _send_text(
        websocket,
        json.dumps({"event": "stop", "streamId": stream_id}),
        playback,
    )


async def _clear_vobiz_audio(
    websocket: WebSocket,
    stream_id: str,
    playback: PlaybackState,
) -> None:
    playback.clear()
    await _send_text(
        websocket,
        json.dumps({"event": "clearAudio", "streamId": stream_id}),
        playback,
    )


async def _send_playback(
    websocket: WebSocket,
    playback: PlaybackState,
) -> None:
    """Pace audio writes to avoid a large OS/Vobiz playback backlog."""
    while True:
        frame = await playback.queue.get()
        if not await _send_text(websocket, frame, playback):
            return
        await asyncio.sleep(PLAY_SEND_INTERVAL_SECONDS)


async def _relay_agent_audio(
    websocket: WebSocket,
    bridge: Any,
    call_id: str,
    stream_id: str,
    playback: PlaybackState,
) -> None:
    """Receive ElevenLabs continuously while a separate task writes to Vobiz."""
    sender = asyncio.create_task(
        _send_playback(websocket, playback),
        name=f"vobiz-playback-{call_id}",
    )
    try:
        while not playback.socket_closed:
            event = await bridge.receive_event(call_id)
            if event.kind == "closed":
                logger.warning(
                    "ElevenLabs connection closed while Vobiz call %s was active",
                    call_id,
                )
                playback.clear()
                await _stop_vobiz_stream(websocket, stream_id, playback)
                return
            if event.kind == "interruption":
                playback.suppress_agent_audio = True
                await _clear_vobiz_audio(websocket, stream_id, playback)
                logger.info("ElevenLabs confirmed interruption for call %s", call_id)
                continue
            if event.kind == "agent_response":
                playback.suppress_agent_audio = False
                playback.barge_in_latched = False
                playback.barge_in_frames = 0
                continue
            if event.kind != "audio" or not event.audio:
                continue
            if playback.suppress_agent_audio:
                continue
            try:
                playback.enqueue_audio(stream_id, event.audio)
            except asyncio.QueueFull:
                logger.error("Vobiz playback queue overflow for call %s", call_id)
                playback.clear()
                await _stop_vobiz_stream(websocket, stream_id, playback)
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Agent-to-Vobiz relay failed for call %s", call_id)
        playback.clear()
        await _stop_vobiz_stream(websocket, stream_id, playback)
    finally:
        sender.cancel()
        with suppress(asyncio.CancelledError):
            await sender


async def _handle_local_barge_in(
    websocket: WebSocket,
    bridge: Any,
    call_id: str,
    stream_id: str,
    playback: PlaybackState,
    audio: bytes,
    input_format: str,
) -> None:
    """Clear queued speech as soon as the caller talks over the agent."""
    if not playback.is_active() or playback.barge_in_latched:
        playback.barge_in_frames = 0
        return
    level = bridge.audio_level(audio, input_format)
    if level < BARGE_IN_RMS_THRESHOLD:
        playback.barge_in_frames = 0
        return
    playback.barge_in_frames += 1
    if playback.barge_in_frames < BARGE_IN_TRIGGER_FRAMES:
        return

    playback.barge_in_latched = True
    playback.suppress_agent_audio = True
    await _clear_vobiz_audio(websocket, stream_id, playback)
    logger.info(
        "Local barge-in cleared Vobiz playback for call %s (level=%d)",
        call_id,
        level,
    )


@router.websocket("/ws/voice/{call_id}")
async def voice_websocket(websocket: WebSocket, call_id: str) -> None:
    await websocket.accept()

    settings = get_settings()
    payment_id = websocket.query_params.get("payment_id", "").strip()
    supplied_signature = websocket.query_params.get("signature", "")
    callback_token = settings.voice_callback_token.strip()
    expected_signature = (
        callback_signature(callback_token, payment_id, call_id)
        if callback_token and payment_id
        else ""
    )
    if not expected_signature or not compare_digest(
        supplied_signature, expected_signature
    ):
        logger.warning("Rejected unauthorized Vobiz stream for call %s", call_id)
        with suppress(Exception):
            await websocket.close(code=4403)
        return

    session = SessionLocal()
    try:
        attempt = session.get(CallAttempt, call_id)
    except Exception:
        logger.exception("Could not load call attempt %s for the Vobiz stream", call_id)
        session.rollback()
        session.close()
        with suppress(Exception):
            await websocket.close(code=1011)
        return

    if (
        attempt is None
        or attempt.provider != "vobiz"
        or attempt.payment_id != payment_id
    ):
        session.close()
        logger.warning("Rejected Vobiz stream for unknown call %s", call_id)
        with suppress(Exception):
            await websocket.close(code=4404)
        return
    if attempt.status in {"CLOSED", "FAILED", "CANCELLED"}:
        session.close()
        logger.warning(
            "Rejected Vobiz stream for inactive call %s (status=%s)",
            call_id,
            attempt.status,
        )
        with suppress(Exception):
            await websocket.close(code=4409)
        return

    bridge = _load_bridge(call_id, settings)
    output_task: asyncio.Task[None] | None = None
    playback = PlaybackState()
    stream_id: str | None = None
    input_format = "mulaw-8k-mono"

    try:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                playback.socket_closed = True
                break
            except Exception:
                playback.socket_closed = True
                logger.exception("Vobiz receive failed for call %s", call_id)
                break

            if message.get("type") == "websocket.disconnect":
                playback.socket_closed = True
                break
            text = message.get("text")
            if not text:
                continue
            try:
                event = json.loads(text)
            except (TypeError, ValueError):
                logger.warning("Ignored invalid Vobiz JSON for call %s", call_id)
                continue
            if not isinstance(event, dict):
                continue

            event_type = event.get("event")
            if event_type == "start":
                if stream_id is not None:
                    logger.warning("Ignored duplicate Vobiz start for call %s", call_id)
                    continue
                start = event.get("start")
                if not isinstance(start, dict):
                    logger.warning("Vobiz start payload was invalid for call %s", call_id)
                    break
                stream_id = str(start.get("streamId") or "").strip()
                if not stream_id:
                    logger.warning("Vobiz start omitted streamId for call %s", call_id)
                    break
                input_format = _format_label(start.get("mediaFormat"))
                if attempt.provider_call_id is None and start.get("callId"):
                    attempt.provider_call_id = str(start["callId"])
                if attempt.status in {"QUEUED", "PLACED"}:
                    attempt.status = "BRIDGED"
                try:
                    session.commit()
                except Exception:
                    logger.exception("Could not mark call %s as bridged", call_id)
                    session.rollback()

                logger.info(
                    "Vobiz stream started for call %s (format=%s)",
                    call_id,
                    input_format,
                )
                if bridge is None or not await bridge.connect(call_id):
                    logger.warning(
                        "Stopping Vobiz stream for call %s because ElevenLabs is unavailable",
                        call_id,
                    )
                    await _stop_vobiz_stream(websocket, stream_id, playback)
                    break
                output_task = asyncio.create_task(
                    _relay_agent_audio(
                        websocket,
                        bridge,
                        call_id,
                        stream_id,
                        playback,
                    ),
                    name=f"elevenlabs-output-{call_id}",
                )
                continue

            if event_type == "media":
                if stream_id is None or bridge is None:
                    continue
                media = event.get("media")
                if not isinstance(media, dict):
                    continue
                if media.get("track", "inbound") != "inbound":
                    continue
                encoded = media.get("payload")
                if not isinstance(encoded, str) or not encoded:
                    continue
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (binascii.Error, ValueError):
                    logger.warning("Ignored invalid Vobiz audio for call %s", call_id)
                    continue
                if raw:
                    await _handle_local_barge_in(
                        websocket,
                        bridge,
                        call_id,
                        stream_id,
                        playback,
                        raw,
                        input_format,
                    )
                    if not await bridge.send_audio(call_id, raw, input_format):
                        logger.warning(
                            "Stopping Vobiz stream after ElevenLabs send failed for call %s",
                            call_id,
                        )
                        await _stop_vobiz_stream(websocket, stream_id, playback)
                        break
                continue

            if event_type in {"playedStream", "clearedAudio"}:
                logger.debug("Vobiz %s received for call %s", event_type, call_id)
                continue

            logger.debug(
                "Ignored unsupported Vobiz event %s for call %s",
                event_type,
                call_id,
            )
    finally:
        playback.socket_closed = True
        playback.clear()
        if output_task is not None:
            output_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await output_task
        if bridge is not None:
            with suppress(Exception):
                await bridge.aclose(call_id)
        try:
            if attempt.status in {"BRIDGED", "PLACED", "QUEUED"}:
                attempt.status = "CLOSED"
                attempt.closed_at = datetime.now(UTC)
                session.commit()
        except Exception:
            logger.exception("Could not close call attempt %s", call_id)
            session.rollback()
        finally:
            session.close()
        logger.info("Vobiz stream closed for call %s", call_id)
