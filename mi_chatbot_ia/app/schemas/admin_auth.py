# app/schemas/admin_auth.py
from pydantic import BaseModel, EmailStr, Field, constr # type: ignore
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Schemas para Role ---
class RoleBase(BaseModel):
    name: constr(min_length=3, max_length=50) = Field(..., description="Nombre único del rol (ej. superadmin, context_editor)") # type: ignore
    description: Optional[str] = Field(None, description="Descripción detallada del rol.")

class RoleCreate(RoleBase):
    pass # Por ahora, la creación es igual a la base

class RoleUpdate(BaseModel): # Todos los campos opcionales para actualizar un rol
    name: Optional[constr(min_length=3, max_length=50)] = None # type: ignore
    description: Optional[str] = None

class RoleResponse(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Schemas para AppUser (Usuarios de Administración) ---
class AppUserBase(BaseModel):
    username_ad: constr(min_length=1, max_length=255) = Field(..., description="Identificador de AD (ej. DNI o sAMAccountName)") # type: ignore
    email: Optional[EmailStr] = Field(None, description="Email del usuario (puede venir de AD).")
    full_name: Optional[str] = Field(None, max_length=255, description="Nombre completo del usuario (puede venir de AD).")
    is_active_local: bool = Field(True, description="Si el usuario está activo en este sistema (independiente de AD).")

class AppUserCreateInternal(AppUserBase): # Usado internamente por el sistema, ej. al provisionar desde AD
    # No esperamos password aquí si la autenticación primaria es siempre AD
    pass

class AppUserUpdateByAdmin(BaseModel): # Para que un superadmin actualice otro usuario
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    is_active_local: Optional[bool] = None
    mfa_enabled: Optional[bool] = None # Permitir a un admin habilitar/deshabilitar MFA para otro (con precaución)
    role_ids: Optional[List[int]] = Field(None, description="Lista COMPLETA de IDs de roles a asignar. Los no incluidos se desasociarán.")

class AppUserResponse(AppUserBase):
    id: int
    mfa_enabled: bool
    roles: List[RoleResponse] = [] # Devolver los roles asignados
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Schemas para Autenticación (Login y Tokens) ---
class ADLoginRequestSchema(BaseModel):
    username: str = Field(..., description="Nombre de usuario (DNI en tu caso) para autenticación AD.")
    password: str = Field(..., description="Contraseña del usuario para autenticación AD.")

class MFARequiredResponseSchema(BaseModel):
    mfa_required: bool = True
    message: str = "Autenticación de Active Directory exitosa. Se requiere verificación MFA."
    # El token pre-MFA se enviará en una cabecera o de otra forma, no necesariamente en el cuerpo JSON
    # O podrías incluirlo aquí si es más fácil para tu frontend:
    # pre_mfa_token: Optional[str] = None 


class MFAVerifyRequestSchema(BaseModel):
    username_ad: str = Field(..., description="El DNI o username_ad del usuario para el cual se verifica el código MFA.")
    mfa_code: constr(pattern=r"^[0-9]{6}$", min_length=6, max_length=6) = Field(..., description="Código TOTP de 6 dígitos.") # type: ignore
    
class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Opcional: Podrías incluir aquí info básica del usuario logueado o un `user_id`
    # user_info: Optional[AppUserResponse] = None
    # expires_in: int # El cliente puede calcularlo o el servidor puede devolverlo

class TokenPayloadSchema(BaseModel): # Para los datos que van DENTRO del JWT
    sub: str # Subject: username_ad (DNI) o el app_user.id
    exp: Optional[datetime] = None # No necesario si se calcula al crear
    iat: Optional[datetime] = None # No necesario si se calcula al crear
    roles: Optional[List[str]] = [] # Nombres de los roles
    mfa_completed: bool = False # Indica si la sesión ha completado MFA
    token_type: Optional[str] = Field(None, description="Tipo de token (ej. 'session', 'pre_mfa')")


# --- Schemas para Configuración de MFA por el Usuario ---
class MFASetupInitiateResponseSchema(BaseModel):
    otpauth_url: str = Field(..., description="URL otpauth:// para generar el código QR (el frontend puede generar el QR).")
    # Opcionalmente, si el backend genera la imagen del QR:
    # qr_code_data_url: Optional[str] = Field(None, description="Data URL de la imagen del código QR (base64).")
    message: str = "Escanea este código QR con tu aplicación autenticadora y verifica con el código generado."

class MFASetupConfirmRequestSchema(BaseModel):
    mfa_code: constr(min_length=6, max_length=6, pattern=r"^[0-9]{6}$") = Field(..., description="Código TOTP de 6 dígitos para confirmar y activar MFA.")# type: ignore

class MFARequiredResponseSchema(BaseModel):
    mfa_required: bool = True
    username_ad: str = Field(..., description="El username_ad (DNI) del usuario que requiere MFA.")
    message: str = "Autenticación de Active Directory exitosa. Se requiere verificación MFA."
    # pre_mfa_token: Optional[str] = None # Podríamos añadir si es necesario    

class PreMFATokenResponseSchema(BaseModel): # Para cuando el login AD es ok, pero se necesita MFA
    status: str = "mfa_required"
    username_ad: str = Field(..., description="El username_ad (DNI) del usuario que requiere verificación MFA.")
    pre_mfa_token: str = Field(..., description="Token JWT temporal para ser usado en el endpoint de verificación MFA.")
    token_type: str = "bearer_pre_mfa" # Indica que es un token pre-MFA
    message: str = "Autenticación de Directorio Activo exitosa. Se requiere verificación de segundo factor (MFA)."
