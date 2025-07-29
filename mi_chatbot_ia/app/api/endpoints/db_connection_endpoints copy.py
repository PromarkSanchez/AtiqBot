# app/api/db_connection_endpoints.py
import traceback # <--- AÑADE ESTE IMPORT ARRIBA DEL TODO

from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore

### NUEVO: Imports adicionales para la inspección ###
import asyncio
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.tools.sql_tools import _get_sync_db_engine


from app.db.session import get_crud_db_session # Sesión para la BD de CRUDs
from app.schemas.schemas import ( # Importa los schemas Pydantic relevantes
    DatabaseConnectionCreate, 
    DatabaseConnectionUpdate, 
    DatabaseConnectionResponse
)



from app.crud import crud_db_connection # Importa los helpers CRUD
# (Asegúrate que app.crud.crud_db_connection realmente exista y tenga las funciones)
from app.models.app_user import AppUser 
from app.security.role_auth import require_roles

# === CORRECCIÓN: Definimos los SCHEMAS DE RESPUESTA aquí arriba ===
class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool

class TableInfo(BaseModel):
    schema_name: Optional[str] = Field(None, description="Nombre del esquema (e.g., 'dbo', 'public')")
    table_name: str
    full_name: str = Field(..., description="Nombre completo, formato 'esquema.tabla'")
    columns: List[ColumnInfo]

class DbInspectionResponse(BaseModel):
    connection_name: str
    tables: List[TableInfo]
# === FIN DE LA CORRECCIÓN ===

# Ejemplo para context_definition_endpoints.py
ROLES_MANAGE_DBCONN  = ["SuperAdmin", "ConectionEditor"] # Quizás ContextEditor también puede gestionar contextos
ROLES_VIEW_CONTEXTS = ["SuperAdmin", "ContextEditor", "LogViewer"] 

MENU_DB_CONNECTIONS = "Conexiones a BD"

router = APIRouter(
    prefix="/api/v1/admin/db_connections", # Prefijo para los endpoints de admin
    tags=["Admin - Database Connections"]  # Etiqueta para Swagger UI
)

@router.post("/", response_model=DatabaseConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_db_connection(
    conn_in: DatabaseConnectionCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DB_CONNECTIONS)) # O SUPERADMIN_ONLY

):
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' Creando conection.")

    """
    Crea una nueva configuración de conexión a base de datos.
    La contraseña se recibirá en texto plano y se encriptará antes de guardar.
    """
    existing_conn = await crud_db_connection.get_db_connection_by_name(db, name=conn_in.name)
    if existing_conn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una conexión de BD con el nombre '{conn_in.name}'."
        )
    
    new_conn = await crud_db_connection.create_db_connection(db=db, conn_in=conn_in)
    return new_conn # Pydantic mapeará el objeto ORM a DatabaseConnectionResponse


@router.get("/", response_model=List[DatabaseConnectionResponse])
async def read_all_db_connections(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DB_CONNECTIONS)) # O SUPERADMIN_ONLY
):
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' Listando conection.")
    """
    Obtiene una lista de todas las configuraciones de conexión a BD.
    (No se devuelven contraseñas).
    """
    connections = await crud_db_connection.get_db_connections(db=db, skip=skip, limit=limit)
    return connections


@router.get("/{conn_id}", response_model=DatabaseConnectionResponse)
async def read_db_connection_by_id(
    conn_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DB_CONNECTIONS)) # O SUPERADMIN_ONLY
):
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' Listando conection.""/{conn_id}")
    """
    Obtiene una configuración de conexión a BD por su ID.
    (No se devuelve contraseña).
    """
    db_conn = await crud_db_connection.get_db_connection_by_id(db=db, conn_id=conn_id)
    if db_conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuración de conexión de BD no encontrada.")
    return db_conn


@router.put("/{conn_id}", response_model=DatabaseConnectionResponse)
async def update_existing_db_connection(
    conn_id: int,
    conn_update: DatabaseConnectionUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DB_CONNECTIONS)) # O SUPERADMIN_ONLY
):
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' Actualizando conection.""/{conn_id}")

    """
    Actualiza una configuración de conexión de BD existente.
    Si se provee una nueva contraseña, se encriptará y reemplazará la anterior.
    """
    db_conn = await crud_db_connection.get_db_connection_by_id(db=db, conn_id=conn_id)
    if db_conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuración de conexión de BD no encontrada.")
    
    # Verificar si el nuevo nombre (si se cambia) ya existe para otro registro
    if conn_update.name and conn_update.name != db_conn.name:
        existing_name_conn = await crud_db_connection.get_db_connection_by_name(db, name=conn_update.name)
        if existing_name_conn and existing_name_conn.id != conn_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe otra conexión de BD con el nombre '{conn_update.name}'."
            )

    updated_conn = await crud_db_connection.update_db_connection(db=db, db_conn_obj=db_conn, conn_in=conn_update)
    return updated_conn


@router.delete("/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_db_connection_entry(
    conn_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DB_CONNECTIONS)) # O SUPERADMIN_ONLY
):
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' eliminando conection.""/{conn_id}")

    """
    Elimina una configuración de conexión de BD.
    """
    deleted_conn = await crud_db_connection.delete_db_connection(db=db, conn_id=conn_id)
    if deleted_conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuración de conexión de BD no encontrada.")
    return None # No Content


# ===========================================================
#         NUEVO ENDPOINT Y LÓGICA DE INSPECCIÓN
# ===========================================================

def inspect_database_sync(engine: Engine) -> List[TableInfo]:
    """Función síncrona que realiza la inspección de la BD. Diseñada para correr en un hilo."""
    inspector = inspect(engine)
    all_tables_info: List[TableInfo] = []
    
    try:
        schemas = inspector.get_schema_names()
    except Exception as e:
        print(f"WARN: No se pudieron listar esquemas (puede ser normal en algunos SGBD o por permisos): {e}")
        schemas = []
    
    default_schema = inspector.default_schema_name
    schemas_to_check = {s for s in schemas}
    schemas_to_check.add(default_schema)
    schemas_to_check.add(None)

    for schema in schemas_to_check:
        try:
            tables_in_schema = inspector.get_table_names(schema=schema)
            for table_name in tables_in_schema:
                try:
                    columns_raw = inspector.get_columns(table_name, schema=schema)
                    columns_info = [
                        ColumnInfo(name=col['name'], type=str(col['type']), nullable=col['nullable'])
                        for col in columns_raw
                    ]
                    
                    full_name = f"{schema}.{table_name}" if schema else table_name
                    
                    all_tables_info.append(TableInfo(
                        schema_name=schema, table_name=table_name,
                        full_name=full_name, columns=columns_info
                    ))
                except Exception as e_col:
                    print(f"WARN: Error inspeccionando columnas para tabla '{schema}.{table_name}': {e_col}")
                    continue
        except Exception as e_table:
            print(f"WARN: Error inspeccionando tablas en esquema '{schema}': {e_table}")
            continue
            
    return all_tables_info


@router.get(
    "/{conn_id}/inspect",
    response_model=DbInspectionResponse,
    summary="Inspeccionar una Conexión para listar Tablas y Columnas"
)
async def inspect_db_connection_endpoint(
    conn_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_MANAGE_DBCONN))
):
    """
    Se conecta a la base de datos de destino y devuelve una lista de sus tablas, esquemas y columnas.
    Endpoint esencial para configurar contextos de tipo DATABASE_QUERY.
    """
    db_conn_config = await crud_db_connection.get_db_connection_by_id(db, conn_id)
    if not db_conn_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuración de conexión de BD no encontrada.")

    sync_engine = None
    try:
        print("\n--- DEBUG: INICIANDO INSPECCIÓN DE BD ---")
        print(f"Intentando crear motor para conexión ID={conn_id}, Nombre='{db_conn_config.name}'")

        sync_engine = _get_sync_db_engine(db_conn_config, context_for_log="API_INSPECT")
        print("Motor de conexión síncrono creado exitosamente.")
        print("Ejecutando la función de inspección en un hilo separado...")

        tables_data = await asyncio.to_thread(inspect_database_sync, sync_engine)
        print(f"Inspección completada. Se encontraron {len(tables_data)} tablas.")
        print("--- DEBUG: FIN INSPECCIÓN DE BD (ÉXITO) ---\n")

    except Exception as e:
        # --- BLOQUE DE CAPTURA DE ERROR MEJORADO ---
        print("\n--- DEBUG: ¡¡¡ERROR DURANTE LA INSPECCIÓN DE BD!!! ---")
        error_type = type(e).__name__
        error_message = str(e)
        
        print(f"Tipo de error: {error_type}")
        print(f"Mensaje: {error_message}")
        print("Traceback completo:")
        traceback.print_exc() # Esto imprimirá el stacktrace completo en tu consola del backend
        
        # Generamos un mensaje de error más específico para el frontend
        detailed_error = f"Fallo al inspeccionar la base de datos. Tipo de error: {error_type}. Mensaje: {error_message}"
        print("--- DEBUG: FIN INSPECCIÓN DE BD (FALLO) ---\n")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo durante la conexión o inspección de la base de datos: {e}"
        )
    finally:
        # Crucial para no dejar conexiones abiertas en el pool
        if sync_engine:
            sync_engine.dispose()
        
    return DbInspectionResponse(
        connection_name=db_conn_config.name,
        tables=tables_data
    )