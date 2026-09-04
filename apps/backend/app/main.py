import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_tools import router as agent_tools_router
from app.api.auth import router as auth_router
from app.api.stripe import payment_router, router as stripe_router
from app.api.voice import router as voice_router
from app.api.voice_demo import router as voice_demo_router
from app.api.voice_ws import router as voice_ws_router
from app.api.webhooks import router as webhooks_router
from app.core.config import get_settings

settings = get_settings()


def _configure_application_logging() -> None:
    """Make `app.*` lifecycle/tool logs visible under Uvicorn and local runs."""
    application_logger = logging.getLogger("app")
    application_logger.setLevel(logging.INFO)
    if not application_logger.handlers:
        uvicorn_handlers = logging.getLogger("uvicorn.error").handlers
        if uvicorn_handlers:
            application_logger.handlers = list(uvicorn_handlers)
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(levelname)s %(name)s: %(message)s")
            )
            application_logger.addHandler(handler)
    application_logger.propagate = False


_configure_application_logging()
app = FastAPI(title="Voic API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(stripe_router, prefix="/api/v1")
app.include_router(payment_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(voice_demo_router, prefix="/api/v1")
app.include_router(agent_tools_router, prefix="/api")
app.include_router(voice_ws_router)


@app.get("/health")
def health() -> dict[str, str]:
    """
    Health check endpoint for service monitoring.

    Returns:
        A dictionary with status "ok".
    """
    return {"status": "ok"}
