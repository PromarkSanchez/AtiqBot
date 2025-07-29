# app/crud/crud_interaction_log.py (Versión Corregida y Robusta)

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.interaction_log import InteractionLog as InteractionLogModel
from typing import Dict, Any

async def create_interaction_log_async(db: AsyncSession, log_data: Dict[str, Any]) -> InteractionLogModel:
    """Crea un log de interacción de forma asíncrona y robusta."""
    print(f"CRUD: Intentando crear log con datos: {log_data.get('user_message')}")
    try:
        # FILTRO DE SEGURIDAD: Solo pasamos al modelo las claves que realmente existen en su tabla.
        model_keys = InteractionLogModel.__table__.columns.keys()
        filtered_log_data = {k: v for k, v in log_data.items() if k in model_keys}
        
        db_log_entry = InteractionLogModel(**filtered_log_data)
        db.add(db_log_entry)
        await db.commit()
        await db.refresh(db_log_entry)
        
        print(f"CRUD: Log guardado. ID: {db_log_entry.id}")
        return db_log_entry
    except Exception as e:
        print(f"CRUD: ERROR al crear log: {e}")
        await db.rollback() # Hacemos rollback si algo falla.
        raise