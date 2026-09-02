from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.merchant import Merchant
from app.models.user import User
from app.schemas.auth import IdentityResponse, LoginRequest, MerchantResponse, SignupRequest
from app.services.auth import create_session, get_current_user, hash_password, normalize_email, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    return get_current_user(request, db, settings)


def identity_response(user: User) -> IdentityResponse:
    return IdentityResponse(user=user, merchant=user.merchant)


@router.post("/signup", response_model=IdentityResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> IdentityResponse:
    email = normalize_email(payload.email)
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    merchant = Merchant(name=payload.merchant_name)
    user = User(email=email, password_hash=hash_password(payload.password), merchant=merchant)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from error

    db.refresh(user)
    return identity_response(user)


@router.post("/login", response_model=IdentityResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IdentityResponse:
    email = normalize_email(payload.email)
    user = db.scalar(select(User).options(joinedload(User.merchant)).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    raw_token = create_session(db, user, settings)
    db.commit()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return identity_response(user)


@router.get("/me", response_model=IdentityResponse)
def me(user: User = Depends(current_user)) -> IdentityResponse:
    return identity_response(user)


@router.get("/merchants/{merchant_id}", response_model=MerchantResponse)
def get_merchant(merchant_id: str, user: User = Depends(current_user)) -> MerchantResponse:
    if merchant_id != user.merchant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    return MerchantResponse.model_validate(user.merchant)
