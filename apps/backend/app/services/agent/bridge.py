"""Full-duplex Vobiz to ElevenLabs conversational audio bridge."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import struct
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

try:  # Python <= 3.12 ships audioop; 3.13+ removed it.
    import audioop  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python 3.13+
    audioop = None  # type: ignore[assignment]

CONVERSATION_WS_HOST = "wss://api.elevenlabs.io"
CONVERSATION_WS_PATH = "/v1/convai/conversation"
SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
SIGNED_URL_TIMEOUT_SECONDS = 10
VOBIZ_SAMPLE_RATE = 8000
DEFAULT_ELEVENLABS_FORMAT = "pcm_16000"
CHANNELS = 1
SAMPLE_WIDTH = 2

ZERO_DECIMAL_CURRENCIES = frozenset(
    {
        "bif",
        "clp",
        "djf",
        "gnf",
        "jpy",
        "kmf",
        "krw",
        "mga",
        "pyg",
        "rwf",
        "ugx",
        "vnd",
        "vuv",
        "xaf",
        "xof",
        "xpf",
    }
)

_MULAW_BIAS = 0x84
_MULAW_CLIP = 32635


@dataclass(frozen=True, slots=True)
class BridgeEvent:
    """One actionable server event for the Vobiz socket."""

    kind: str
    audio: bytes = b""


def conversation_ws_url(agent_id: str) -> str:
    """Return the public-agent WebSocket URL (mainly useful for diagnostics)."""
    return f"{CONVERSATION_WS_HOST}{CONVERSATION_WS_PATH}?{urlencode({'agent_id': agent_id})}"


def _connection_error_label(error: Exception) -> str:
    """Return actionable connection detail without URLs, tokens, or payloads."""
    if isinstance(error, HTTPError):
        return f"HTTP {error.code}"
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        return f"HTTP {status_code}"
    return type(error).__name__


def _signed_conversation_ws_url(api_key: str, agent_id: str) -> str:
    """Request a short-lived URL so private agent credentials never enter WS logs."""
    request = Request(
        f"{SIGNED_URL_ENDPOINT}?{urlencode({'agent_id': agent_id})}",
        headers={"xi-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    with urlopen(request, timeout=SIGNED_URL_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))
    signed_url = payload.get("signed_url") if isinstance(payload, dict) else None
    if not isinstance(signed_url, str):
        raise TypeError("signed URL response did not contain signed_url")
    parsed = urlparse(signed_url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "wss" or not (
        hostname == "api.elevenlabs.io" or hostname.endswith(".elevenlabs.io")
    ):
        raise RuntimeError("signed URL response used an unexpected host")
    return signed_url


def call_context(call_id: str, settings: Any = None) -> dict[str, str]:
    """Load merchant-scoped payment variables bound to this call attempt."""
    try:
        from collections.abc import Mapping

        from sqlalchemy import select

        from app.core.database import SessionLocal
        from app.models.call_attempt import CallAttempt
        from app.models.payment import Payment
        from app.models.payment_event import PaymentEvent

        with SessionLocal() as session:
            attempt = session.get(CallAttempt, call_id)
            if attempt is None:
                return {}
            payment = session.scalar(
                select(Payment).where(
                    Payment.id == attempt.payment_id,
                    Payment.merchant_id == attempt.merchant_id,
                )
            )
            variables = {
                "payment_id": attempt.payment_id,
                "merchant_id": attempt.merchant_id,
                "customer_phone": attempt.customer_phone or "",
                # Speech-safe product label; NEVER read payment_id on a call.
                "product_name": "recent order",
            }
            if payment is None:
                return variables

            currency = (payment.currency or "").lower()
            variables["amount"] = (
                str(payment.amount)
                if currency in ZERO_DECIMAL_CURRENCIES
                else f"{payment.amount / 100:g}"
            )
            variables["currency"] = payment.currency or ""

            if payment.provider_payment_id:
                event = session.scalar(
                    select(PaymentEvent)
                    .where(
                        PaymentEvent.merchant_id == attempt.merchant_id,
                        PaymentEvent.provider_connection_id
                        == payment.provider_connection_id,
                        PaymentEvent.provider_payment_id
                        == payment.provider_payment_id,
                        PaymentEvent.customer_email.is_not(None),
                    )
                    .order_by(PaymentEvent.occurred_at.desc())
                    .limit(1)
                )
                if event is not None and event.customer_email:
                    variables["customer_email"] = event.customer_email

            if payment.provider_price_id and settings is not None:
                try:
                    from app.services.providers.stripe import StripeProvider

                    price = StripeProvider(settings).get_price(
                        payment.provider_account_id, payment.provider_price_id
                    )
                    product = price.get("product") if isinstance(price, Mapping) else None
                    name = product.get("name") if isinstance(product, Mapping) else None
                    if isinstance(name, str) and name.strip():
                        variables["product_name"] = name.strip()
                except Exception:
                    logger.debug(
                        "Voice bridge product lookup failed for call %s",
                        call_id,
                        exc_info=True,
                    )
            return variables
    except Exception:
        logger.warning(
            "Voice bridge could not load call context for call %s",
            call_id,
            exc_info=True,
        )
        return {}


# ---------------------------------------------------------------------------
# Audio conversion
# ---------------------------------------------------------------------------


def _build_ulaw_decode_table() -> list[int]:
    table = []
    for byte in range(256):
        value = (~byte) & 0xFF
        sign = value & 0x80
        exponent = (value >> 4) & 0x07
        mantissa = value & 0x0F
        sample = ((mantissa << 3) + _MULAW_BIAS) << exponent
        sample -= _MULAW_BIAS
        table.append(-sample if sign else sample)
    return table


_ULAW_DECODE_TABLE = _build_ulaw_decode_table()


def _ulaw_to_lin_pure(data: bytes) -> bytes:
    if not data:
        return b""
    return struct.pack(f"<{len(data)}h", *(_ULAW_DECODE_TABLE[byte] for byte in data))


def _lin_to_ulaw_pure(data: bytes) -> bytes:
    if not data:
        return b""
    sample_count = len(data) // 2
    samples = struct.unpack(f"<{sample_count}h", data[: sample_count * 2])
    output = bytearray(sample_count)
    for index, sample in enumerate(samples):
        clipped = max(-_MULAW_CLIP, min(_MULAW_CLIP, sample))
        output[index] = min(
            range(256), key=lambda code: abs(_ULAW_DECODE_TABLE[code] - clipped)
        )
    return bytes(output)


def _resample_pcm16(data: bytes, input_rate: int, output_rate: int) -> bytes:
    if not data or input_rate == output_rate:
        return bytes(data)
    sample_count = len(data) // 2
    if sample_count == 0:
        return b""
    samples = struct.unpack(f"<{sample_count}h", data[: sample_count * 2])
    output_count = round(sample_count * output_rate / input_rate)
    if output_count <= 0:
        return b""
    if sample_count == 1:
        return struct.pack(f"<{output_count}h", *([samples[0]] * output_count))
    output: list[int] = []
    for index in range(output_count):
        position = index * input_rate / output_rate
        lower = int(position)
        if lower >= sample_count - 1:
            output.append(samples[-1])
            continue
        fraction = position - lower
        output.append(
            int(samples[lower] + (samples[lower + 1] - samples[lower]) * fraction)
        )
    return struct.pack(f"<{len(output)}h", *output)


def _ulaw2lin(data: bytes) -> bytes:
    if audioop is not None:
        return audioop.ulaw2lin(data, SAMPLE_WIDTH)
    return _ulaw_to_lin_pure(data)


def _lin2ulaw(data: bytes) -> bytes:
    if audioop is not None:
        return audioop.lin2ulaw(data, SAMPLE_WIDTH)
    return _lin_to_ulaw_pure(data)


def _ratecv(data: bytes, input_rate: int, output_rate: int) -> bytes:
    if audioop is not None:
        converted, _ = audioop.ratecv(
            data,
            SAMPLE_WIDTH,
            CHANNELS,
            input_rate,
            output_rate,
            None,
        )
        return converted
    return _resample_pcm16(data, input_rate, output_rate)


def _pcm_format_rate(format_name: str, default: int = 16000) -> int:
    normalized = (format_name or "").strip().lower()
    if normalized.startswith("pcm_"):
        try:
            return int(normalized.removeprefix("pcm_"))
        except ValueError:
            pass
    return default


def _vobiz_pcm(audio: bytes, format_label: str) -> tuple[bytes, int]:
    label = (format_label or "").lower()
    if "pcm" in label:
        return bytes(audio), 16000 if "16k" in label else 8000
    return _ulaw2lin(audio), VOBIZ_SAMPLE_RATE


def _encode_caller_audio(
    audio: bytes, format_label: str, target_format: str
) -> str:
    target = (target_format or DEFAULT_ELEVENLABS_FORMAT).lower()
    if target == "ulaw_8000" and "mulaw" in (format_label or "").lower():
        encoded = bytes(audio)
    else:
        pcm, input_rate = _vobiz_pcm(audio, format_label)
        if target == "ulaw_8000":
            encoded = _lin2ulaw(_ratecv(pcm, input_rate, VOBIZ_SAMPLE_RATE))
        else:
            encoded = _ratecv(pcm, input_rate, _pcm_format_rate(target))
    return base64.b64encode(encoded).decode("ascii")


def vobiz_audio_level(audio: bytes, format_label: str) -> int:
    """Return a codec-independent PCM RMS level for local barge-in detection."""
    pcm, _ = _vobiz_pcm(audio, format_label)
    if not pcm:
        return 0
    if audioop is not None:
        return audioop.rms(pcm, SAMPLE_WIDTH)
    sample_count = len(pcm) // SAMPLE_WIDTH
    if sample_count == 0:
        return 0
    samples = struct.unpack(f"<{sample_count}h", pcm[: sample_count * SAMPLE_WIDTH])
    return int((sum(sample * sample for sample in samples) / sample_count) ** 0.5)


def vobiz_to_elevenlabs(audio: bytes) -> str:
    """Backward-compatible conversion to the default PCM16/16 kHz format."""
    return _encode_caller_audio(audio, "mulaw-8k-mono", DEFAULT_ELEVENLABS_FORMAT)


def elevenlabs_to_vobiz(
    raw: bytes, source_format: str = DEFAULT_ELEVENLABS_FORMAT
) -> bytes:
    """Convert negotiated ElevenLabs output into Vobiz μ-law/8 kHz."""
    if not raw:
        return b""
    normalized = (source_format or DEFAULT_ELEVENLABS_FORMAT).lower()
    if normalized == "ulaw_8000":
        return bytes(raw)
    source_rate = _pcm_format_rate(normalized)
    return _lin2ulaw(_ratecv(bytes(raw), source_rate, VOBIZ_SAMPLE_RATE))


# ---------------------------------------------------------------------------
# Full-duplex bridge
# ---------------------------------------------------------------------------


class VoiceBridge:
    """Maintain one persistent ElevenLabs conversation per Vobiz call."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._api_key = str(getattr(settings, "elevenlabs_api_key", "") or "").strip()
        self._agent_id = str(getattr(settings, "elevenlabs_agent_id", "") or "").strip()
        self._connections: dict[str, Any] = {}
        self._send_locks: dict[str, asyncio.Lock] = {}
        self._conversation_ids: dict[str, str] = {}
        self._input_formats: dict[str, str] = {}
        self._output_formats: dict[str, str] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._agent_id)

    async def connect(self, call_id: str) -> bool:
        """Open and initialize the private ElevenLabs agent conversation."""
        if call_id in self._connections:
            return True
        if not self.is_configured:
            logger.warning(
                "Voice bridge disabled for call %s: ElevenLabs credentials are missing",
                call_id,
            )
            return False
        try:
            signed_url = await asyncio.to_thread(
                _signed_conversation_ws_url, self._api_key, self._agent_id
            )
            try:
                from websockets.asyncio.client import connect as ws_connect
            except ImportError:
                from websockets import connect as ws_connect  # type: ignore[no-redef]

            websocket = await ws_connect(
                signed_url,
                open_timeout=SIGNED_URL_TIMEOUT_SECONDS,
                ping_interval=None,
                max_size=2**20,
            )
            self._connections[call_id] = websocket
            self._send_locks[call_id] = asyncio.Lock()
            variables = await asyncio.to_thread(call_context, call_id, self._settings)
            await self._send_json(
                call_id,
                {
                    "type": "conversation_initiation_client_data",
                    "dynamic_variables": variables,
                },
            )
            logger.info("Voice bridge connected to ElevenLabs for call %s", call_id)
            return True
        except Exception as error:  # noqa: BLE001 - external HTTP/WS boundary
            logger.error(
                "Voice bridge could not connect call %s to ElevenLabs (%s)",
                call_id,
                _connection_error_label(error),
            )
            await self.aclose(call_id)
            return False

    def audio_level(self, audio: bytes, format_label: str) -> int:
        """Measure caller energy without network or database work."""
        return vobiz_audio_level(audio, format_label)

    async def send_audio(self, call_id: str, audio: bytes, format_label: str) -> bool:
        """Forward one caller chunk without waiting for an agent response."""
        if not audio:
            return True
        if call_id not in self._connections and not await self.connect(call_id):
            return False
        try:
            payload = _encode_caller_audio(
                audio,
                format_label,
                self._input_formats.get(call_id, DEFAULT_ELEVENLABS_FORMAT),
            )
            # ElevenLabs' raw WebSocket protocol has no `type` wrapper here.
            await self._send_json(call_id, {"user_audio_chunk": payload})
            return True
        except Exception as error:  # noqa: BLE001 - external WebSocket boundary
            logger.error(
                "Voice bridge failed to send caller audio for call %s (%s)",
                call_id,
                _connection_error_label(error),
            )
            await self.aclose(call_id)
            return False

    async def receive_event(self, call_id: str) -> BridgeEvent:
        """Wait for the next audio/control event relevant to Vobiz."""
        websocket = self._connections.get(call_id)
        if websocket is None:
            return BridgeEvent("closed")
        while True:
            try:
                message = await websocket.recv()
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 - external WebSocket boundary
                logger.warning(
                    "Voice bridge receive loop ended for call %s (%s)",
                    call_id,
                    _connection_error_label(error),
                )
                return BridgeEvent("closed")

            event = await self._parse_server_message(call_id, message)
            if event is not None:
                return event

    async def on_vobiz_audio(
        self, call_id: str, audio: bytes, format: str
    ) -> bytes | None:
        """Compatibility hook: production uses `send_audio` + `receive_event`."""
        await self.send_audio(call_id, audio, format)
        return None

    async def on_elevenlabs_audio(self, call_id: str, audio: bytes) -> None:
        """Compatibility hook retained for the frozen bridge interface."""
        logger.debug(
            "Received externally supplied ElevenLabs audio for call %s (%d bytes)",
            call_id,
            len(audio or b""),
        )

    async def aclose(self, call_id: str) -> None:
        websocket = self._connections.pop(call_id, None)
        self._send_locks.pop(call_id, None)
        self._conversation_ids.pop(call_id, None)
        self._input_formats.pop(call_id, None)
        self._output_formats.pop(call_id, None)
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001 - best-effort external cleanup
                logger.debug("Voice bridge close failed for call %s", call_id)

    async def _send_json(self, call_id: str, payload: dict[str, Any]) -> None:
        websocket = self._connections.get(call_id)
        if websocket is None:
            raise RuntimeError("ElevenLabs conversation is not connected")
        lock = self._send_locks.setdefault(call_id, asyncio.Lock())
        async with lock:
            await websocket.send(json.dumps(payload))

    async def _parse_server_message(
        self, call_id: str, message: Any
    ) -> BridgeEvent | None:
        if isinstance(message, (bytes, bytearray)):
            audio = elevenlabs_to_vobiz(
                bytes(message),
                self._output_formats.get(call_id, DEFAULT_ELEVENLABS_FORMAT),
            )
            return BridgeEvent("audio", audio) if audio else None

        try:
            payload = json.loads(message)
        except (TypeError, ValueError):
            logger.warning("Voice bridge received invalid JSON for call %s", call_id)
            return None
        if not isinstance(payload, dict):
            return None

        conversation_id = _find_conversation_id(payload)
        if conversation_id:
            await self._note_conversation_id(call_id, conversation_id)

        event_type = str(payload.get("type") or "")
        if event_type == "conversation_initiation_metadata":
            metadata = payload.get("conversation_initiation_metadata_event")
            if isinstance(metadata, dict):
                input_format = metadata.get("user_input_audio_format")
                output_format = metadata.get("agent_output_audio_format")
                if isinstance(input_format, str):
                    self._input_formats[call_id] = input_format
                if isinstance(output_format, str):
                    self._output_formats[call_id] = output_format
                logger.info(
                    "ElevenLabs conversation initialized for call %s (input=%s, output=%s)",
                    call_id,
                    self._input_formats.get(call_id, DEFAULT_ELEVENLABS_FORMAT),
                    self._output_formats.get(call_id, DEFAULT_ELEVENLABS_FORMAT),
                )
            return None

        if event_type == "ping":
            ping = payload.get("ping_event")
            event_id = ping.get("event_id") if isinstance(ping, dict) else None
            pong: dict[str, Any] = {"type": "pong"}
            if event_id is not None:
                pong["event_id"] = event_id
            await self._send_json(call_id, pong)
            return None

        if event_type == "audio":
            encoded = _find_audio_b64(payload)
            if not encoded:
                return None
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                logger.warning(
                    "Voice bridge received invalid audio payload for call %s", call_id
                )
                return None
            audio = elevenlabs_to_vobiz(
                raw,
                self._output_formats.get(call_id, DEFAULT_ELEVENLABS_FORMAT),
            )
            return BridgeEvent("audio", audio) if audio else None

        if event_type == "interruption":
            return BridgeEvent("interruption")

        if event_type == "agent_response":
            return BridgeEvent("agent_response")

        if event_type in {"agent_tool_response", "agent_tool_response_full_payload"}:
            tool = payload.get(event_type)
            if isinstance(tool, dict):
                log = logger.warning if tool.get("is_error") else logger.info
                log(
                    "ElevenLabs webhook tool %s for call %s: %s",
                    tool.get("tool_name") or "unknown",
                    call_id,
                    "failed" if tool.get("is_error") else "completed",
                )
            return None

        if event_type == "client_tool_call":
            await self._reject_client_tool(call_id, payload)
            return None

        if event_type == "client_error":
            details = payload.get("client_error")
            code = details.get("code") if isinstance(details, dict) else None
            logger.error(
                "ElevenLabs reported a client error for call %s (code=%s)",
                call_id,
                code or "unknown",
            )
            return None

        return None

    async def _reject_client_tool(self, call_id: str, payload: dict[str, Any]) -> None:
        tool = payload.get("client_tool_call")
        if not isinstance(tool, dict):
            return
        name = str(tool.get("tool_name") or "unknown")
        tool_call_id = tool.get("tool_call_id")
        logger.error(
            "ElevenLabs requested client tool %s for call %s; configure it as a webhook tool",
            name,
            call_id,
        )
        if tool.get("expects_response") and isinstance(tool_call_id, str):
            await self._send_json(
                call_id,
                {
                    "type": "client_tool_result",
                    "tool_call_id": tool_call_id,
                    "result": "Tool is configured incorrectly; use a webhook tool",
                    "is_error": True,
                },
            )

    async def _note_conversation_id(
        self, call_id: str, conversation_id: str
    ) -> None:
        if self._conversation_ids.get(call_id) == conversation_id:
            return
        self._conversation_ids[call_id] = conversation_id
        await asyncio.to_thread(_persist_conversation_id, call_id, conversation_id)


def _find_audio_b64(event: dict[str, Any]) -> str | None:
    nested = event.get("audio_event")
    if not isinstance(nested, dict):
        return None
    value = nested.get("audio_base_64")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _find_conversation_id(event: dict[str, Any]) -> str | None:
    for key in ("conversation_id", "conversationId"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("conversation_initiation_metadata_event", "metadata", "data"):
        nested = event.get(key)
        if isinstance(nested, dict):
            found = _find_conversation_id(nested)
            if found:
                return found
    return None


def _persist_conversation_id(call_id: str, conversation_id: str) -> None:
    try:
        from sqlalchemy import update

        from app.core.database import SessionLocal
        from app.models.call_attempt import CallAttempt

        with SessionLocal() as session:
            session.execute(
                update(CallAttempt)
                .where(CallAttempt.id == call_id)
                .values(elevenlabs_conversation_id=conversation_id)
            )
            session.commit()
    except Exception:
        logger.warning(
            "Voice bridge could not persist the ElevenLabs conversation for call %s",
            call_id,
            exc_info=True,
        )


def get_bridge(settings: Any) -> VoiceBridge | None:
    """Create a bridge only when the WebSocket credentials are configured."""
    bridge = VoiceBridge(settings)
    if not bridge.is_configured:
        logger.warning(
            "Voice bridge disabled: ELEVENLABS_API_KEY/ELEVENLABS_AGENT_ID not set"
        )
        return None
    return bridge
