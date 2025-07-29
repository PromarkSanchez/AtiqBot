# app/api/endpoints/admin_auth_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Response # type: ignore
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from typing import Any, Optional, List, Union,Dict

from app.db.session import get_crud_db_session
# Asegurarse de que todos los schemas necesarios están definidos en admin_auth.py
from app.schemas.admin_auth import (
    TokenSchema, 
    PreMFATokenResponseSchema,   # Para la respuesta 202 del login
    # MFARequiredResponseSchema, # No se usa directamente como response_model, PreMFATokenResponseSchema lo cubre mejor
    MFASetupInitiateResponseSchema,
    MFASetupConfirmRequestSchema,
    MFAVerifyRequestSchema,      # Para el cuerpo de /verify-mfa
    TokenPayloadSchema           # Para el tipado del payload del token
)

 
from app.services.ad_auth_service import ADAuthService
from app.services.app_user_service import AppUserService # Usado para get_or_create
from app.services.mfa_service import MFAService
from app.security import jwt_utils 
from app.crud import crud_app_user 
from app.models.app_user import AppUser 
from app.config import settings 
# No necesitamos importar pydantic.BaseModel etc. aquí si ya están en los schemas

router = APIRouter(
    prefix="/api/v1/admin/auth", 
    tags=["Admin - Auth & Users"] # Tag para OpenAPI
)

# --- Instancias de Servicios (singleton para la carga del módulo) ---
ad_auth_service = ADAuthService() 
app_user_service = AppUserService() 
mfa_service = MFAService()

# --- OAuth2 Security Scheme ---
# Se usa en la dependencia get_current_active_admin_user para el token de sesión completo.
# El tokenUrl apunta al endpoint de login que genera el token.
oauth2_scheme_session = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login") 

# --- Dependencia para Obtener el Usuario Administrador Autenticado ---
async def get_current_active_admin_user(
    token: str = Depends(oauth2_scheme_session), 
    db: AsyncSession = Depends(get_crud_db_session)
) -> AppUser:
    """
    Valida el token JWT de sesión.
    Asegura que sea un token de tipo "session" y que MFA (si está habilitado para el usuario)
    esté marcado como completado en el token. Devuelve el objeto AppUser.
    """
    credentials_exception_auth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales (token inválido, expirado o tipo incorrecto).",
        headers={"WWW-Authenticate": "Bearer"},
    )
    credentials_exception_mfa = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, # 403 porque está autenticado pero no autorizado por MFA
        detail="Se requiere completar la verificación MFA para esta acción.",
    )
    
    token_payload = jwt_utils.decode_access_token(token) # Devuelve TokenPayloadSchema o None

    if token_payload is None:
        raise credentials_exception_auth
    
    # Verificar el tipo de token esperado para una sesión completa
    if token_payload.token_type != "session":
        print(f"ADMIN_AUTH_DEPENDENCY: Token de tipo '{token_payload.token_type}' recibido, se esperaba 'session'.")
        raise credentials_exception_auth
    
    # El 'sub' del token de sesión es el username_ad (DNI)
    username_ad_from_token: Optional[str] = token_payload.sub
    if not username_ad_from_token:
        raise credentials_exception_auth
    
    user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=username_ad_from_token)
    if user is None:
        # Usuario en el token pero no en BD (podría haber sido borrado)
        raise credentials_exception_auth
    if not user.is_active_local:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta de usuario inactiva.")
    
    # Crucial: Si MFA está habilitado para este usuario en la BD, el token debe confirmarlo
    if user.mfa_enabled and not token_payload.mfa_completed:
        print(f"ADMIN_AUTH_DEPENDENCY: ALERTA - Usuario {user.username_ad} tiene MFA habilitado pero el token de sesión no indica mfa_completed=true.")
        raise credentials_exception_mfa # MFA fue requerida pero el token no lo refleja como completado
        
    return user

# --- Endpoint de Login Principal (AD + Manejo de MFA) ---
@router.post("/login", 
             response_model=Union[TokenSchema, PreMFATokenResponseSchema], 
             responses={
                 status.HTTP_200_OK: {"model": TokenSchema, "description": "Login exitoso, token de sesión completo emitido (MFA no activado o ya verificado)."},
                 status.HTTP_202_ACCEPTED: {"model": PreMFATokenResponseSchema, "description": "Autenticación AD OK, pero MFA es requerida. Se devuelve un token pre-MFA."},
                 status.HTTP_401_UNAUTHORIZED: {"description": "Credenciales AD inválidas o usuario local inactivo/no encontrado."}
             })
async def login_admin_with_ad_and_handle_mfa(
    response: Response, # Para poder setear status_code
    form_data: OAuth2PasswordRequestForm = Depends(), # Espera 'username' (DNI) y 'password'
    db: AsyncSession = Depends(get_crud_db_session)
):
    admin_dni_input = form_data.username
    admin_ad_password = form_data.password
    print(f"ADMIN_LOGIN_ENDPOINT: Intento de login AD para DNI: {admin_dni_input}")

    # 1. Autenticar contra Active Directory
    ad_user_attributes = ad_auth_service.authenticate_user_and_get_attributes(
        dni_as_username_input=admin_dni_input, password=admin_ad_password
    )
    if not ad_user_attributes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales de Active Directory incorrectas.")
    print(f"ADMIN_LOGIN_ENDPOINT: Autenticación AD exitosa para DNI: {admin_dni_input}.")

    # 2. Obtener o crear el AppUser local, y verificar si está activo
    app_user_instance = await app_user_service.get_or_create_user_after_ad_auth(
        db=db, ad_attributes=ad_user_attributes, dni_input=admin_dni_input
    )
    if not app_user_instance or not app_user_instance.is_active_local:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario local no autorizado o inactivo.")
    print(f"ADMIN_LOGIN_ENDPOINT: Usuario local ID {app_user_instance.id} (username_ad: {app_user_instance.username_ad}) OK.")

    # 3. Flujo basado en si MFA está habilitado para el usuario local
    if app_user_instance.mfa_enabled:
        print(f"ADMIN_LOGIN_ENDPOINT: MFA habilitado para {app_user_instance.username_ad}. Devolviendo respuesta con token Pre-MFA.")
        pre_mfa_jwt_str = jwt_utils.create_pre_mfa_token(user_identifier=app_user_instance.username_ad)
        
        response.status_code = status.HTTP_202_ACCEPTED 
        return PreMFATokenResponseSchema(
            username_ad=app_user_instance.username_ad,
            pre_mfa_token=pre_mfa_jwt_str
        )
    else: # MFA NO está habilitado para este usuario
        print(f"ADMIN_LOGIN_ENDPOINT: MFA NO habilitado para {app_user_instance.username_ad}. Generando token de sesión completo.")
        user_local_roles = [role.name for role in app_user_instance.roles] if app_user_instance.roles else []
        session_jwt_str = jwt_utils.create_session_token(
            user_identifier=app_user_instance.username_ad, # 'sub' será el DNI/username_ad
            roles=user_local_roles
        )
        # El código de estado 200 OK es el default aquí
        return TokenSchema(access_token=session_jwt_str, token_type="bearer")


# --- NUEVO ENDPOINT: Verificar Código MFA después del Login AD Exitoso ---
@router.post("/verify-mfa", response_model=TokenSchema,
             responses={
                 status.HTTP_400_BAD_REQUEST: {"description": "Código MFA inválido, expirado o datos de entrada incorrectos."},
                 status.HTTP_401_UNAUTHORIZED: {"description": "Fallo en la identificación del usuario o MFA no habilitado cuando se esperaba."},
                 status.HTTP_404_NOT_FOUND: {"description": "Usuario no encontrado para el username_ad provisto."},
                 status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Error interno con el secreto MFA."}
             })
async def verify_mfa_code_after_ad_login( # Nombre de función más descriptivo
    mfa_verify_payload: MFAVerifyRequestSchema, # Recibe { "username_ad": "dni", "mfa_code": "123456" }
    db: AsyncSession = Depends(get_crud_db_session)
):
    """
    Verifica el código TOTP para un usuario que ha pasado la autenticación AD
    y para el cual se requiere MFA. Si el código es válido, emite el token de sesión completo.
    """
    print(f"ADMIN_VERIFY_MFA_ENDPOINT: Verificando código '{mfa_verify_payload.mfa_code}' para usuario AD: {mfa_verify_payload.username_ad}")

    # Identificar al usuario
    # NO se usa un token Bearer pre-MFA aquí, se confía en que el frontend maneja el flujo
    # y envía el username_ad correcto del paso de login. 
    # Se podría añadir protección con el pre_mfa_token si se desea más seguridad aquí.
    app_user_to_verify = await crud_app_user.get_app_user_by_username_ad(db, username_ad=mfa_verify_payload.username_ad)
    
    if not app_user_to_verify:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario '{mfa_verify_payload.username_ad}' no encontrado.")
    if not app_user_to_verify.is_active_local:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Usuario '{mfa_verify_payload.username_ad}' está inactivo.")
    if not app_user_to_verify.mfa_enabled:
        print(f"ADVERTENCIA ADMIN_VERIFY_MFA_ENDPOINT: Se intentó verificar MFA para usuario '{mfa_verify_payload.username_ad}' que no lo tiene habilitado.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA no está configurado como requerido para este usuario.")
    if not app_user_to_verify.mfa_secret_encrypted:
        print(f"ERROR CRÍTICO ADMIN_VERIFY_MFA_ENDPOINT: Usuario '{mfa_verify_payload.username_ad}' tiene MFA habilitado pero no tiene secreto MFA en BD.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de configuración interna de MFA.")

    decrypted_mfa_secret_for_user = await crud_app_user.get_decrypted_mfa_secret(db_user=app_user_to_verify)
    if not decrypted_mfa_secret_for_user or decrypted_mfa_secret_for_user == "[DATO ENCRIPTADO INVÁLIDO O ERROR DE DESENCRIPTACIÓN]":
        # Este log es importante para el admin del sistema
        print(f"ERROR CRÍTICO ADMIN_VERIFY_MFA_ENDPOINT: No se pudo desencriptar el secreto MFA para usuario {app_user_to_verify.username_ad}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al procesar su configuración de seguridad.")

    is_user_code_valid = mfa_service.verify_mfa_code(
        mfa_secret_base32_for_user=decrypted_mfa_secret_for_user,
        code_from_user=mfa_verify_payload.mfa_code
    )

    if not is_user_code_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El código MFA proporcionado es inválido o ha expirado.")

    # ¡Código MFA Válido! Ahora sí, emitir el token de sesión completo.
    print(f"ADMIN_VERIFY_MFA_ENDPOINT: Código MFA validado para {app_user_to_verify.username_ad}. Generando token de sesión completo.")
    app_user_roles_names = [role.name for role in app_user_to_verify.roles] if app_user_to_verify.roles else []
    session_complete_access_token = jwt_utils.create_session_token(
        user_identifier=app_user_to_verify.username_ad,
        roles=app_user_roles_names,
        mfa_enabled=app_user_to_verify.mfa_enabled,  # Pasamos el estado real (será True)
        mfa_verified_in_this_flow=True               # Confirmamos que se acaba de verificar
    )
    return TokenSchema(access_token=session_complete_access_token, token_type="bearer")


# --- Endpoints para Configuración de MFA por el Usuario (ya los tenías y deberían funcionar) ---
@router.post("/mfa/setup-initiate", response_model=MFASetupInitiateResponseSchema)
async def mfa_setup_initiate_for_current_user( # Nombre de función clarificado
    current_user: AppUser = Depends(get_current_active_admin_user), 
    db: AsyncSession = Depends(get_crud_db_session)
):
    if current_user.mfa_enabled: # Si ya lo tiene, no puede iniciar setup de nuevo a menos que lo deshabilite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail="MFA ya está habilitado. Para reconfigurar, deshabilite primero (si la funcionalidad existe).")

    print(f"MFA_SETUP_INITIATE_ENDPOINT: Para usuario: {current_user.username_ad}")
    secret_base32, otpauth_url_str = mfa_service.generate_new_mfa_details(username_for_uri=current_user.username_ad)
    
    try: # Guardar el secreto encriptado (mfa_enabled sigue False hasta confirmar)
        await crud_app_user.update_app_user_mfa_secret(db, db_user=current_user, mfa_secret_plain=secret_base32)
        print(f"MFA_SETUP_INITIATE_ENDPOINT: Secreto MFA guardado (encriptado) para {current_user.username_ad}.")
    except ValueError as ve: # Ej. si FERNET_KEY no está
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ve))
    
    return MFASetupInitiateResponseSchema(otpauth_url=otpauth_url_str)


@router.post("/mfa/setup-confirm", 
             response_model=Dict[str, str], # Respuesta simple como {"message": "..."}
             status_code=status.HTTP_200_OK)
async def mfa_setup_confirm_for_current_user( # Nombre de función clarificado
    mfa_confirm_payload: MFASetupConfirmRequestSchema, # Cuerpo: { "mfa_code": "123456" }
    
    current_user: AppUser = Depends(get_current_active_admin_user), 
    db: AsyncSession = Depends(get_crud_db_session)
):
   
   

    print(f"MFA_SETUP_CONFIRM_ENDPOINT: Para usuario: {current_user.username_ad}, código: {mfa_confirm_payload.mfa_code}")
    if current_user.mfa_enabled: # Si durante este proceso ya se habilitó
        return {"message": "MFA ya se encuentra activo y verificado para este usuario."}
        
    if not current_user.mfa_secret_encrypted:
        # Esto significa que /mfa/setup-initiate no se llamó o falló al guardar el secreto.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail="El proceso de configuración de MFA no se ha iniciado correctamente (falta secreto temporal). Por favor, intente iniciar el setup de nuevo.")

    decrypted_user_secret_str = await crud_app_user.get_decrypted_mfa_secret(db_user=current_user)
    if not decrypted_user_secret_str or decrypted_user_secret_str == "[DATO ENCRIPTADO INVÁLIDO O ERROR DE DESENCRIPTACIÓN]":
        print(f"ERROR CRÍTICO MFA_SETUP_CONFIRM_ENDPOINT: No se pudo desencriptar el secreto MFA para usuario {current_user.username_ad}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno con su configuración de seguridad MFA.")

    is_user_provided_code_valid = mfa_service.verify_mfa_code(
        mfa_secret_base32_for_user=decrypted_user_secret_str,
        code_from_user=mfa_confirm_payload.mfa_code
    )
    if not is_user_provided_code_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El código de verificación MFA proporcionado es inválido o ha expirado.")

    # Si el código es válido, AHORA SÍ activar MFA para el usuario en la BD
    await crud_app_user.set_app_user_mfa_status(db, db_user=current_user, enabled=True)
    print(f"MFA_SETUP_CONFIRM_ENDPOINT: MFA activado y confirmado para usuario {current_user.username_ad}.")
    
    await db.refresh(current_user, attribute_names=['mfa_enabled'])
    print(f"MFA_SETUP_CONFIRM_ENDPOINT: MFA activado y confirmado para usuario {current_user.username_ad}.")
    
    return {"message": "MFA configurado y activado exitosamente en su cuenta."}