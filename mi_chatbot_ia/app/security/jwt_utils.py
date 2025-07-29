# app/security/jwt_utils.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union, List

from jose import JWTError, jwt
from pydantic import ValidationError

from app.config import settings
from app.schemas.schemas import TokenPayloadSchema # <-- AHORA IMPORTAMOS DE TU ARCHIVO ÚNICO

ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
PRE_MFA_TOKEN_EXPIRE_MINUTES = settings.JWT_PRE_MFA_TOKEN_EXPIRE_MINUTES
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_pre_mfa_token(user_identifier: Union[str, int]) -> str:
    expires = timedelta(minutes=PRE_MFA_TOKEN_EXPIRE_MINUTES)
    token_payload = TokenPayloadSchema(
        sub=str(user_identifier),
        token_type="pre-mfa"
    )
    return create_access_token(data=token_payload.model_dump(), expires_delta=expires)

def create_session_token(
    user_identifier: Union[str, int], 
    roles: Optional[List[str]],
    mfa_enabled: bool,
    mfa_verified_in_this_flow: bool = False
) -> str:
    expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    is_mfa_session_complete = not mfa_enabled or mfa_verified_in_this_flow
    token_payload = TokenPayloadSchema(
        sub=str(user_identifier),
        token_type="session",
        roles=roles if roles else [],
        mfa_enabled=mfa_enabled,
        mfa_completed=is_mfa_session_complete
    )
    return create_access_token(data=token_payload.model_dump(), expires_delta=expires)

def decode_access_token(token: str) -> Optional[TokenPayloadSchema]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayloadSchema(**payload)
    except (JWTError, ValidationError) as e:
        print(f"Error decodificando o validando token: {e}")
        return None