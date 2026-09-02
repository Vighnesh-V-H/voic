from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    merchant_name: str = Field(min_length=1, max_length=120)

    @field_validator("merchant_name")
    @classmethod
    def merchant_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("merchant_name must not be blank")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr


class MerchantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class IdentityResponse(BaseModel):
    user: UserResponse
    merchant: MerchantResponse
