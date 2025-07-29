# app/api/endpoints/admin_utility_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import asyncio # Para asyncio.to_thread

from app.db.session import get_crud_db_session
from app.crud import crud_db_connection # Para obtener el DBConnectionConfig
from app.models.app_user import AppUser
from app.security.role_auth import require_roles
# Asumimos que tu sql_tools está en app/tools/sql_tools.py y tiene la lógica
from app.tools import sql_tools # Necesitaremos adaptar esto

router = APIRouter(
    prefix="/api/v1/admin/utils",
    tags=["Admin - Utilities"]
)

ROLES_CAN_USE_UTILS = ["SuperAdmin", "ContextEditor"] # Define quién puede usar estas utilidades

class TestQueryRequest(BaseModel):
    query_string: str

class TestQueryResponse(BaseModel):
    success: bool
    message: str
    row_count: Optional[int] = None
    preview_data: Optional[List[Dict[str, Any]]] = None
    error_detail: Optional[str] = None

@router.get(
    "/db-connections/{conn_id}/list-tables", 
    response_model=List[str],
    summary="List Tables and Views from a DB Connection"
)
async def list_tables_from_db_connection(
    conn_id: int,
    db_crud: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_USE_UTILS)),
):
    db_conn_config = await crud_db_connection.get_db_connection_by_id(db_crud, conn_id=conn_id)
    if not db_conn_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DB Connection Config no encontrada.")

    # La lógica para listar tablas es específica del dialecto de la BD
    # y actualmente está implícita en tu `generate_ddl_for_tables_directly`
    # o requeriría una nueva función en sql_tools o aquí.
    # Esto es un placeholder, necesitaríamos una función robusta.
    try:
        # Simulación: Esto DEBERÍA ser una función en sql_tools que se conecte y liste
        # Por ahora, si tienes generate_ddl_for_tables_directly que REFLEJA tablas,
        # podrías usar eso o una adaptación para solo obtener nombres.
        # Aquí devolvemos una lista de ejemplo, DEBES IMPLEMENTAR ESTO.
        
        # Ejemplo de cómo podría ser con una función que SÍ lista tablas
        # table_names = await asyncio.to_thread(
        #     sql_tools.get_table_names_from_connection, # NECESITAS CREAR ESTA FUNCIÓN
        #     db_conn_config
        # )
        # return table_names

        # Placeholder si la función no existe aún:
        if db_conn_config.db_type.value == "SQLSERVER":
            return ["dbo.MiTablaEjemplo1", "Ventas.VistaProductos", "dbo.OtraTabla"]
        elif db_conn_config.db_type.value == "POSTGRESQL":
            return ["public.mi_tabla_pg", "another_schema.vista_pg"]
        else:
            return [] # O lanzar un error si el tipo no es soportado para listado
            
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                            detail=f"Error al listar tablas para conexión '{db_conn_config.name}': {str(e)}")

@router.post(
    "/db-connections/{conn_id}/test-dictionary-query",
    response_model=TestQueryResponse,
    summary="Test a Dictionary Table Query against a DB Connection"
)
async def test_dictionary_query_on_db_connection(
    conn_id: int,
    request_body: TestQueryRequest,
    db_crud: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_USE_UTILS)),
):
    db_conn_config = await crud_db_connection.get_db_connection_by_id(db_crud, conn_id=conn_id)
    if not db_conn_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DB Connection Config no encontrada.")

    if not request_body.query_string or not request_body.query_string.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query inválida o no es SELECT.")

    try:
        # Tu fetch_data_from_db es síncrona, la ejecutamos en un thread
        # Asumo que sql_tools.fetch_data_from_db existe y es la misma que tenías en tu script de ingesta
        
        # Esta función debería estar en sql_tools y tomar db_conn_config
        # data = await asyncio.to_thread(
        #     sql_tools.execute_generic_select_query, # NECESITAS CREAR/ADAPTAR ESTA FUNCIÓN
        #     db_conn_config, 
        #     request_body.query_string,
        #     limit=5 # Limitar a 5 filas para el preview
        # )

        # Usando tu `fetch_data_from_db` del script de ingesta (que necesita estar en `sql_tools.py`)
        # Debes asegurarte que `sql_tools` ahora contenga una función similar a `fetch_data_from_db`
        # que tome `DatabaseConnectionConfig` y `query_string`.
        if not hasattr(sql_tools, 'fetch_data_from_db'):
             raise NotImplementedError("La función 'fetch_data_from_db' no está disponible en sql_tools.")

        # Es síncrona, así que la corremos en un thread
        data_rows: List[Dict[str, Any]] = await asyncio.to_thread(
            sql_tools.fetch_data_from_db, db_conn_config, request_body.query_string # Asegúrate que los params coincidan
        )

        return TestQueryResponse(
            success=True,
            message="Query ejecutada exitosamente.",
            row_count=len(data_rows),
            preview_data=data_rows[:5] # Devuelve solo las primeras 5 filas como preview
        )
    except ValueError as ve: # Por ejemplo, si _get_sync_db_engine falla
        return TestQueryResponse(success=False, message=str(ve), error_detail=str(ve))
    except Exception as e:
        # Idealmente, sql_tools.fetch_data_from_db devolvería un error específico o None en caso de fallo
        # Aquí capturamos una excepción genérica.
        print(f"Error en test_dictionary_query: {e}")
        # import traceback; traceback.print_exc() # Para debug
        return TestQueryResponse(success=False, message="Error al ejecutar la query de prueba.", error_detail=str(e))