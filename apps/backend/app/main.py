from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.stripe import payment_router, router as stripe_router
from app.api.webhooks import router as webhooks_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Voic API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(stripe_router, prefix="/api/v1")
app.include_router(payment_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
