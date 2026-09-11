"""The bridge must surface WebSocket close code/reason in error labels.

Regression context: live calls were cut with zero conversation because
ElevenLabs closed the conversation WS with 3000/quota_exceeded, but the
backend only logged the exception type name, making a billing failure
indistinguishable from a bridge fault.
"""

from app.services.agent.bridge import _connection_error_label


class FakeCloseError(Exception):
    """Mimics websockets.exceptions.ConnectionClosed (code/reason attrs)."""

    def __init__(self) -> None:
        super().__init__("received 3000 (registered) [quota_exceeded]")
        self.code = 3000
        self.reason = "quota_exceeded"


def test_close_code_and_reason_surface_in_label():
    label = _connection_error_label(FakeCloseError())
    assert "3000" in label
    assert "quota_exceeded" in label


def test_plain_errors_still_label_by_type():
    assert _connection_error_label(ValueError("nope")) == "ValueError"
