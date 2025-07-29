# app/security/api_key_auth.py
import json
from fastapi import HTTPException, Security, Depends, status, Header
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Annotated # Annotated para FastAPI >= 0.95

from app.crud import crud_api_client # Importa el módulo CRUD
from app.crud.crud_api_client import hash_api_key # Importa la función de hashing
from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.schemas.schemas import ApiClientSettingsSchema

API_KEY_NAME = "X-API-Key"
APPLICATION_ID_HEADER_NAME = "X-Application-ID"

# Esquema para el header X-API-Key
api_key_header_scheme = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Esquema para el header X-Application-ID (aunque Header() es más directo)
# application_id_header_scheme = APIKeyHeader(name=APPLICATION_ID_HEADER_NAME, auto_error=False)


async def get_validated_api_client(
    # Usar Annotated para FastAPI >= 0.95 para mejor documentación y type hints
    api_key_header: Annotated[Optional[str], Security(api_key_header_scheme)],
    x_application_id: Annotated[Optional[str], Header(alias=APPLICATION_ID_HEADER_NAME, description=f"Identificador único de la aplicación cliente. Requerido con {API_KEY_NAME}.")],
    db: AsyncSession = Depends(get_crud_db_session)
) -> ApiClientModel: # Retorna el modelo SQLAlchemy con los settings ya parseados y validados (o atributos transitorios)
    """
    Dependencia para validar X-API-Key y X-Application-ID.
    1. Valida que ambos headers estén presentes.
    2. Hashea la API Key recibida.
    3. Busca el ApiClient por la clave hasheada.
    4. Verifica que el ApiClient esté activo.
    5. Parsea los 'settings' del ApiClient para obtener el 'application_id' configurado.
    6. Verifica que el X-Application-ID del header coincida con el configurado.
    
    Retorna la instancia de ApiClientModel si todo es válido.
    Eleva HTTPException en caso de error.
    """
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Cabecera '{API_KEY_NAME}' no proporcionada."
        )
    
    if not x_application_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, # 400 ya que es un parámetro esperado
            detail=f"Cabecera '{APPLICATION_ID_HEADER_NAME}' requerida."
        )

    # 1. Hashear la API Key recibida del header
    #    (Tu función hash_api_key es un placeholder, DEBE ser un hash real y seguro)
    hashed_api_key_from_header = hash_api_key(api_key_header)

    # 2. Buscar el ApiClient por la clave hasheada
    #    La función get_api_client_by_hashed_key ya llama a _prepare_api_client_object_for_response
    api_client_orm_obj = await crud_api_client.get_api_client_by_hashed_key(
        db=db, hashed_api_key=hashed_api_key_from_header
    )

    if not api_client_orm_obj:
        print(f"API_KEY_AUTH: API Key (hash: {hashed_api_key_from_header}) no encontrada o inválida.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, # Era 403, pero 401 es más apropiado para credencial inválida
            detail=f"API Key ('{API_KEY_NAME}') inválida."
        )
    
    if not api_client_orm_obj.is_active:
        print(f"API_KEY_AUTH: ApiClient '{api_client_orm_obj.name}' (ID: {api_client_orm_obj.id}) está inactivo.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cliente API ('{API_KEY_NAME}') inactivo."
        )
        
    print(f"API_KEY_AUTH: API Key válida para ApiClient '{api_client_orm_obj.name}' (ID: {api_client_orm_obj.id})")

    # 3. Validar X-Application-ID contra los settings del ApiClient
    #    _prepare_api_client_object_for_response DEBE haber parseado client_orm_obj.settings (dict de la BD)
    #    y el schema ApiClientResponse (usado implícitamente por FastAPI al retornar)
    #    se encargaría de usar ese dict para el campo `settings: ApiClientSettingsSchema`.
    #    Aquí, necesitamos el `ApiClientSettingsSchema` para la validación.
    
    client_settings_from_orm = api_client_orm_obj.settings # Este es el dict de la BD
    parsed_settings_obj: Optional[ApiClientSettingsSchema] = None

    if isinstance(client_settings_from_orm, dict):
        try:
            parsed_settings_obj = ApiClientSettingsSchema.model_validate(client_settings_from_orm)
        except Exception as e_settings_parse:
            print(f"API_KEY_AUTH: ERROR CRÍTICO - No se pudieron validar los 'settings' (tipo: {type(client_settings_from_orm)}) del ApiClient ID {api_client_orm_obj.id} contra ApiClientSettingsSchema: {e_settings_parse}")
            # Esto indica un problema de configuración en la BD o un error en el schema.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de configuración interna del ApiClient (settings inválidos)."
            )
    elif client_settings_from_orm is None: # Settings es None/vacío en la BD
         print(f"API_KEY_AUTH: ApiClient '{api_client_orm_obj.name}' no tiene 'settings' configurados en la BD.")
    else: # Tipo inesperado (ej. string si JSONB no parseó bien a dict)
        print(f"API_KEY_AUTH: ApiClient '{api_client_orm_obj.name}' tiene 'settings' de tipo inesperado ({type(client_settings_from_orm)}) en la BD.")

    if not parsed_settings_obj or not parsed_settings_obj.application_id:
        # application_id es un campo obligatorio en ApiClientSettingsSchema, por lo que
        # ApiClientSettingsSchema.model_validate(un_dict_vacio) fallaría.
        # Esta condición cubre el caso donde settings en BD sea None o un dict que no pasa la validación.
        print(f"API_KEY_AUTH: ApiClient '{api_client_orm_obj.name}' (ID: {api_client_orm_obj.id}) no tiene un 'application_id' válido en sus settings.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key válida, pero no configurada para ser usada por una aplicación específica (falta application_id en settings)."
        )

    if x_application_id != parsed_settings_obj.application_id:
        print(f"API_KEY_AUTH: X-Application-ID '{x_application_id}' RECIBIDO no coincide con "
              f"el configurado '{parsed_settings_obj.application_id}' para ApiClient '{api_client_orm_obj.name}'.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Identificador de aplicación ('{APPLICATION_ID_HEADER_NAME}') no autorizado para esta API Key."
        )
        
    print(f"API_KEY_AUTH: ApiClient '{api_client_orm_obj.name}' (AppID: '{x_application_id}') VALIDADO correctamente.")
    
    # Para que otras partes del request (como el endpoint del chat) puedan acceder
    # a los settings ya parseados y validados, los adjuntamos al objeto ORM de forma transitoria.
    # Esto es seguro porque `get_validated_api_client` es una dependencia y el objeto
    # no necesariamente se commiteará de nuevo a menos que el endpoint lo modifique.
    setattr(api_client_orm_obj, 'parsed_settings_object', parsed_settings_obj)
    
    return api_client_orm_obj


# Wrapper para usar en Depends() si solo necesitas validar sin usar el objeto
async def verify_api_key_and_app(
    api_client: ApiClientModel = Depends(get_validated_api_client)
) -> None:
    """
    Dependencia simple que solo valida la API Key y Application ID.
    No devuelve el objeto ApiClient, solo permite continuar si la validación es exitosa.
    """
    # Si get_validated_api_client no eleva una excepción, la autenticación es exitosa.
    pass