# app/api/endpoints/admin_auth_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union, Dict

# ### ¡CAMBIO #1: Usamos el nombre correcto de tu fábrica de sesiones! ###
from app.db.session import get_crud_db_session, AsyncSessionLocal_CRUD

from app.models.app_user import AppUser, AuthMethod
from app.schemas.schemas import TokenSchema, PreMFATokenResponseSchema, MFASetupInitiateResponseSchema, MFASetupConfirmRequestSchema, MFAVerifyRequestSchema
from app.services.ad_auth_service import ADAuthService
from app.services.app_user_service import AppUserService
from app.services.mfa_service import MFAService
from app.security import jwt_utils 
from app.crud import crud_app_user 
from app.utils.security_utils import verify_password


router = APIRouter(prefix="/api/v1/admin/auth", tags=["Admin - Auth & Users"])
ad_auth_service = ADAuthService()
app_user_service = AppUserService()
mfa_service = MFAService()
oauth2_scheme_session = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login")

async def get_current_active_admin_user(token: str = Depends(oauth2_scheme_session), db: AsyncSession = Depends(get_crud_db_session)) -> AppUser:
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
    app_user: AppUser | None = None
    
    ad_attributes = ad_auth_service.authenticate_user_and_get_attributes(
        form_data.username, form_data.password
    )

    if ad_attributes:
        existing_user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=form_data.username)
        
        if existing_user:
            if not existing_user.is_active_local:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Su cuenta está desactivada. Contacte a un administrador."
                )
            app_user = existing_user
        else:
            print("INFO: Creando usuario en una transacción independiente...")
            # ### ¡CAMBIO #2: Usamos el nombre correcto de tu fábrica de sesiones! ###
            async with AsyncSessionLocal_CRUD() as independent_db:
                await app_user_service.get_or_create_user_after_ad_auth(
                    independent_db, ad_attributes, form_data.username
                )
                await independent_db.commit()
            
            print("INFO: Usuario guardado. Ahora lanzando error 403.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Su cuenta ha sido creada y está pendiente de activación por un administrador."
            )
    else:
        local_user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=form_data.username)
        if (
            local_user and
            local_user.auth_method == AuthMethod.LOCAL and
            local_user.is_active_local and
            local_user.hashed_password and
            verify_password(form_data.password, local_user.hashed_password)
        ):
            app_user = local_user

    if not app_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    await db.refresh(app_user, ['roles'])
    await db.commit()

    if app_user.mfa_enabled:
        pre_mfa_token = jwt_utils.create_pre_mfa_token(app_user.username_ad)
        response.status_code = status.HTTP_202_ACCEPTED
        return PreMFATokenResponseSchema(username_ad=app_user.username_ad, pre_mfa_token=pre_mfa_token)
    
    roles = [role.name for role in app_user.roles] if app_user.roles else []
    
    session_token = jwt_utils.create_session_token(
        user_identifier=app_user.username_ad,
        roles=roles,
        mfa_enabled=app_user.mfa_enabled,
        mfa_verified_in_this_flow=False
    )
    
    return TokenSchema(access_token=session_token, token_type="bearer")


@router.post("/verify-mfa", response_model=TokenSchema)
async def verify_mfa_code_after_ad_login(payload: MFAVerifyRequestSchema, db: AsyncSession = Depends(get_crud_db_session)):
    user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=payload.username_ad)
    if not user or not user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Configuración MFA inválida para el usuario.")
    
    decrypted_secret = await crud_app_user.get_decrypted_mfa_secret(user)
    if not decrypted_secret:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error interno al procesar el secreto MFA.")
    
    if not mfa_service.verify_mfa_code(decrypted_secret, payload.mfa_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Código MFA inválido.")

    await db.refresh(user, ['roles'])
    roles = [role.name for role in user.roles] if user.roles else []
    
    session_token = jwt_utils.create_session_token(
        user_identifier=user.username_ad,
        roles=roles,
        mfa_enabled=user.mfa_enabled,
        mfa_verified_in_this_flow=True
    )
    return TokenSchema(access_token=session_token, token_type="bearer")


@router.post("/mfa/setup-initiate", response_model=MFASetupInitiateResponseSchema)
async def mfa_setup_initiate(current_user: AppUser = Depends(get_current_active_admin_user), db: AsyncSession = Depends(get_crud_db_session)):
    if current_user.mfa_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "MFA ya está habilitado para este usuario.")
    secret, url = mfa_service.generate_new_mfa_details(current_user.username_ad)
    await crud_app_user.update_app_user_mfa_secret(db, current_user, secret)
    return MFASetupInitiateResponseSchema(otpauth_url=url)


@router.post("/mfa/setup-confirm", response_model=Dict[str, str])
async def mfa_setup_confirm(payload: MFASetupConfirmRequestSchema, current_user: AppUser = Depends(get_current_active_admin_user), db: AsyncSession = Depends(get_crud_db_session)):
    if current_user.mfa_enabled:
        return {"message": "MFA ya se encuentra activo."}
    if not current_user.mfa_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El proceso de configuración de MFA no ha sido iniciado.")
    decrypted_secret = await crud_app_user.get_decrypted_mfa_secret(current_user)
    if not decrypted_secret:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error de configuración de seguridad interna.")
    if not mfa_service.verify_mfa_code(decrypted_secret, payload.mfa_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El código MFA proporcionado es inválido.")
    await crud_app_user.set_app_user_mfa_status(db, current_user, enabled=True)
    return {"message": "MFA activado exitosamente."}