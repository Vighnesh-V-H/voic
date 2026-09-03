from pydantic import BaseModel


class ProviderConnectionResponse(BaseModel):
    provider: str
    connected: bool
