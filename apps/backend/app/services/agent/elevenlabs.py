"""Configuration contract for the ElevenLabs WebSocket agent path.

Vobiz places the phone call and streams caller media to Voic. Voic maintains a
private ElevenLabs conversational WebSocket, relays audio in both directions,
and exposes authenticated webhook tools for business operations.
"""

from app.core.config import Settings


# Payment context variable names passed to the agent per call. The agent's
# first message and tool parameters reference these; Voic verifies them
# against the merchant-owned payment before dialing and on every tool call.
CONTEXT_VARIABLES = frozenset(
    {
        "amount",
        "currency",
        "customer_email",
        "customer_phone",
        "merchant_id",
        "payment_id",
    }
)


def is_configured(settings: Settings) -> bool:
    """Return True when the WebSocket bridge and webhook tools can operate.

    ``ELEVENLABS_PHONE_NUMBER_ID`` belongs to the alternative direct-SIP mode
    and is intentionally not required by this Vobiz media-stream bridge.
    """
    return bool(
        settings.elevenlabs_api_key.strip()
        and settings.elevenlabs_agent_id.strip()
        and settings.agent_tool_token.strip()
    )
