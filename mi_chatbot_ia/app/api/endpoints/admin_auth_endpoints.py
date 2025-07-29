# app/api/endpoints/admin_auth_endpoints.py
# (El contenido completo que te pasé en la respuesta anterior que empieza con "# app/api/endpoints/admin_auth_endpoints.py...")
# Tu archivo original está casi perfecto, solo necesita los ajustes en las llamadas a `create_session_token`
# y el `db.refresh`.
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union, Dict
# AHORA (la corrección):
from app.models.app_user import AppUser, AuthMethod
# Ahora importamos desde el archivo de schemas único
from app.schemas.schemas import (
    TokenSchema, 
    PreMFATokenResponseSchema,
    MFASetupInitiateResponseSchema,
    MFASetupConfirmRequestSchema,
    MFAVerifyRequestSchema,
)

from app.db.session import get_crud_db_session
from app.services.ad_auth_service import ADAuthService
from app.services.app_user_service import AppUserService
from app.services.mfa_service import MFAService
from app.security import jwt_utils 
from app.crud import crud_app_user 
from app.models.app_user import AppUser 
from app.utils.security_utils import verify_password

# No necesitamos importar el get_current_user_... de sí mismo
# Pero si está en otro fichero de dependencias, esa importación es correcta.

router = APIRouter(prefix="/api/v1/admin/auth", tags=["Admin - Auth & Users"])

ad_auth_service = ADAuthService()
app_user_service = AppUserService()
mfa_service = MFAService()

# Re-pego la dependencia de `get_current_active_admin_user` que ya tenías
# para asegurar que esté aquí si no está en otro sitio.
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme_session = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login")

async def get_current_active_admin_user(token: str = Depends(oauth2_scheme_session), db: AsyncSession = Depends(get_crud_db_session)) -> AppUser:
    # ... tu código para esta dependencia, que ya está bien ...
    credentials_exception_auth = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.", headers={"WWW-Authenticate": "Bearer"})
    credentials_exception_mfa = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verificación MFA requerida.")
    token_payload = jwt_utils.decode_access_token(token)
    if not token_payload or token_payload.token_type != "session" or not token_payload.sub: raise credentials_exception_auth
    user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=token_payload.sub)
    if not user or not user.is_active_local: raise credentials_exception_auth
    if user.mfa_enabled and not token_payload.mfa_completed: raise credentials_exception_mfa
    return user


@router.post("/login", response_model=None)
async def login_admin_unificado(
    response: Response, 
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_crud_db_session)
):
    # 1. Buscar al usuario en NUESTRA base de datos primero.
    # El username que viene del formulario es `form_data.username`
    app_user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=form_data.username)

    if not app_user or not app_user.is_active_local:
        # Si el usuario no existe o está inactivo, rechazamos directamente.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.", # Usamos un mensaje genérico
        )
    
    # 2. Verificar la contraseña según el método de autenticación del usuario.
    is_authenticated = False
    if app_user.auth_method == AuthMethod.LOCAL:
        # Autenticación LOCAL
        if app_user.hashed_password and verify_password(form_data.password, app_user.hashed_password):
            is_authenticated = True
    
    elif app_user.auth_method == AuthMethod.AD:
        # Autenticación AD
        # Usamos el nuevo método `validate_credentials` de nuestro servicio.
        if ad_auth_service.validate_credentials(form_data.username, form_data.password):
            is_authenticated = True
            # ¡IMPORTANTE! Si el login con AD es exitoso, actualizamos los datos del usuario.
            # Esto mantiene sincronizados el nombre, email, etc.
            ad_attributes = ad_auth_service.authenticate_user_and_get_attributes(form_data.username, form_data.password)
            if ad_attributes:
                # `get_or_create_user_after_ad_auth` probablemente ya actualiza los datos. Reutilicémoslo.
                app_user = await app_user_service.get_or_create_user_after_ad_auth(db, ad_attributes, form_data.username)

    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )
        
    # 3. Flujo de MFA (ya lo tienes y está perfecto, lo reutilizamos)
    # A partir de aquí, el `app_user` está validado, sin importar el método.
    await db.refresh(app_user, ['roles']) # Es bueno refrescar las relaciones por si acaso.

    if app_user.mfa_enabled:
        pre_mfa_token = jwt_utils.create_pre_mfa_token(app_user.username_ad)
        response.status_code = status.HTTP_202_ACCEPTED
        return PreMFATokenResponseSchema(username_ad=app_user.username_ad, pre_mfa_token=pre_mfa_token)
    
    # Si no tiene MFA, generamos el token de sesión final.
    roles = [role.name for role in app_user.roles] if app_user.roles else []
    session_token = jwt_utils.create_session_token(app_user.username_ad, roles, mfa_enabled=False, mfa_verified_in_this_flow=False)
    
    # IMPORTANTE: `TokenSchema` parece esperar `access_token` y `token_type`
    return TokenSchema(access_token=session_token, token_type="bearer")


@router.post("/verify-mfa", response_model=TokenSchema)
async def verify_mfa_code_after_ad_login(payload: MFAVerifyRequestSchema, db: AsyncSession = Depends(get_crud_db_session)):
    user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=payload.username_ad)
    if not user or not user.mfa_enabled or not user.mfa_secret_encrypted: raise HTTPException(status.HTTP_400_BAD_REQUEST, "Configuración MFA inválida.")
    
    decrypted_secret = await crud_app_user.get_decrypted_mfa_secret(user)
    if not decrypted_secret: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error interno de seguridad.")
    
    if not mfa_service.verify_mfa_code(decrypted_secret, payload.mfa_code): raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código MFA inválido.")

    await db.refresh(user) # <- ¡Crucial!

    roles = [role.name for role in user.roles] if user.roles else []
    session_token = jwt_utils.create_session_token(user.username_ad, roles, mfa_enabled=user.mfa_enabled, mfa_verified_in_this_flow=True)
    return TokenSchema(access_token=session_token, token_type="bearer")


@router.post("/mfa/setup-initiate", response_model=MFASetupInitiateResponseSchema)
async def mfa_setup_initiate(current_user: AppUser = Depends(get_current_active_admin_user), db: AsyncSession = Depends(get_crud_db_session)):
    if current_user.mfa_enabled: raise HTTPException(status.HTTP_400_BAD_REQUEST, "MFA ya habilitado.")
    secret, url = mfa_service.generate_new_mfa_details(current_user.username_ad)
    await crud_app_user.update_app_user_mfa_secret(db, current_user, secret)
    return MFASetupInitiateResponseSchema(otpauth_url=url)


@router.post("/mfa/setup-confirm", response_model=Dict[str, str])
async def mfa_setup_confirm(payload: MFASetupConfirmRequestSchema, current_user: AppUser = Depends(get_current_active_admin_user), db: AsyncSession = Depends(get_crud_db_session)):
    if current_user.mfa_enabled: return {"message": "MFA ya activo."}
    if not current_user.mfa_secret_encrypted: raise HTTPException(status.HTTP_400_BAD_REQUEST, "Proceso MFA no iniciado.")

    decrypted_secret = await crud_app_user.get_decrypted_mfa_secret(current_user)
    if not decrypted_secret: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error de configuración.")

    if not mfa_service.verify_mfa_code(decrypted_secret, payload.mfa_code): raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido.")

    await crud_app_user.set_app_user_mfa_status(db, current_user, enabled=True)
    await db.refresh(current_user, ['mfa_enabled'])
    return {"message": "MFA activado exitosamente."}