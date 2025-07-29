# app/security/jwt_utils.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union, List

from jose import JWTError, jwt
from pydantic import ValidationError

from app.config import settings
# Asegúrate de que este import sea correcto y el schema exista.
from app.schemas.admin_auth import TokenPayloadSchema 

# Opciones de Token
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
PRE_MFA_TOKEN_EXPIRE_MINUTES = settings.JWT_PRE_MFA_TOKEN_EXPIRE_MINUTES
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM


def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """Función genérica para crear un token JWT."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_pre_mfa_token(user_identifier: Union[str, int]) -> str:
    """
    Crea un token JWT de corta duración para la fase pre-MFA.
    Este token no da acceso a nada, solo prueba que el primer factor (contraseña) fue exitoso.
    """
    expires = timedelta(minutes=PRE_MFA_TOKEN_EXPIRE_MINUTES)
    # Creamos un payload válido según TokenPayloadSchema, pero con tipo 'pre-mfa'.
    token_payload = TokenPayloadSchema(
        sub=str(user_identifier),
        token_type="pre-mfa",
        mfa_completed=False, # Explícitamente no completado
        roles=[] # Sin roles, ya que no autoriza nada
    )
    return create_access_token(data=token_payload.model_dump(), expires_delta=expires)


# =========================================================================
# === FUNCIÓN CLAVE MODIFICADA ===
# =========================================================================
def create_session_token(
    user_identifier: Union[str, int], 
    roles: Optional[List[str]],
    mfa_enabled: bool,
    mfa_verified_in_this_flow: bool = False
) -> str:
    """
    Crea un token de sesión completo.
    - mfa_enabled: El estado actual del MFA del usuario en la BD.
    - mfa_verified_in_this_flow: True si el usuario acaba de pasar el reto MFA.
    """
    expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # El claim 'mfa_completed' será True si:
    # 1. El MFA no está habilitado para el usuario.
    # 2. O si el MFA SÍ está habilitado y el usuario lo acaba de verificar en este flujo de login.
    is_mfa_session_complete = not mfa_enabled or mfa_verified_in_this_flow

    token_payload = TokenPayloadSchema(
        sub=str(user_identifier),
        token_type="session",
        roles=roles if roles else [],
        mfa_enabled=mfa_enabled,  # Guardamos el estado real del MFA del usuario
        mfa_completed=is_mfa_session_complete # Guardamos si para esta sesión se considera completo
    )

    return create_access_token(data=token_payload.model_dump(), expires_delta=expires)


def decode_access_token(token: str) -> Optional[TokenPayloadSchema]:
    """
    Decodifica y valida un token JWT.
    Devuelve el payload validado como un objeto TokenPayloadSchema o None si falla.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayloadSchema(**payload)
        return token_data
    except JWTError as e:
        print(f"JWTError al decodificar token: {e}")
        return None
    except ValidationError as e_val:
        print(f"ValidationError al validar payload de token: {e_val}")
        return None
    except Exception as e_unk:
        print(f"Error inesperado al decodificar token: {e_unk}")
        return None