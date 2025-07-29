# app/services/cache_service.py (Versión ASÍNCRONA Final y Robusta)

import json
import hashlib
from typing import Optional, Dict, Any, List

# CAMBIO CLAVE: Usamos la librería oficial de Redis en modo asíncrono
from redis.asyncio import Redis as AsyncRedis

# CAMBIO CLAVE: Importamos el objeto 'settings' para el TTL. Ya no importamos nada de app_state.
from app.config import settings

# ==========================================================
# ===    NUEVO CACHÉ ASÍNCRONO DE RESPUESTAS DE CHAT     ===
# ==========================================================

def _create_secure_cache_key(api_client_id: int, context_ids: List[int], question: str) -> str:
    """Crea una clave de caché segura (esta función no cambia)."""
    sorted_contexts = sorted(list(set(context_ids)))
    key_material = f"{api_client_id}:{','.join(map(str, sorted_contexts))}:{question.lower().strip()}"
    return f"chatbot_response:v3:{hashlib.sha256(key_material.encode()).hexdigest()}"

async def get_cached_response_async(
    redis_client: Optional[AsyncRedis], 
    api_client_id: int, 
    context_ids: List[int], 
    question: str
) -> Optional[Dict[str, Any]]:
    """
    (ASÍNCRONO) Recupera una respuesta de chat cacheada.
    Recibe el cliente redis como parámetro.
    """
    if not redis_client:
        return None

    cache_key = _create_secure_cache_key(api_client_id, context_ids, question)
    
    try:
        # CAMBIO CLAVE: Usamos `await` para la operación de red.
        cached_json = await redis_client.get(cache_key)
        if cached_json:
            print(f"CACHE_HIT: Respuesta de chat encontrada para la clave '{cache_key}'")
            return json.loads(cached_json)
    except Exception as e:
        print(f"CACHE_ERROR: Error al leer de Redis (get_cached_response_async): {e}")

    return None

async def set_cached_response_async(
    redis_client: Optional[AsyncRedis], 
    api_client_id: int, 
    context_ids: List[int], 
    question: str, 
    response_dict: Dict[str, Any]
):
    """(ASÍNCRONO) Guarda una respuesta de chat en la caché."""
    if not redis_client:
        return

    bot_response_text = response_dict.get("bot_response", "")
    if not bot_response_text or "[Error" in bot_response_text:
        print("CACHE_SKIP: Respuesta inválida, no se guardará en caché.")
        return

    cache_key = _create_secure_cache_key(api_client_id, context_ids, question)
    
    try:
        json_value = json.dumps(response_dict)
        # CAMBIO CLAVE: Usamos `await`
        await redis_client.set(cache_key, json_value, ex=settings.CACHE_EXPIRATION_SECONDS)
        print(f"CACHE_SET: Respuesta de chat guardada para la clave '{cache_key}'")
    except Exception as e:
        print(f"CACHE_ERROR: Error al escribir en Redis (set_cached_response_async): {e}")


# ==========================================================
# ===    NUEVO CACHÉ ASÍNCRONO GENÉRICO (PARA ESTADO)    ===
# ==========================================================
# Reemplaza tus funciones set_cache, get_cache, delete_cache.

async def set_generic_cache_async(
    redis_client: Optional[AsyncRedis],
    key: str, 
    value: Any, 
    ttl_seconds: Optional[int] = None
) -> bool:
    """(ASÍNCRONO) Guarda un valor genérico en Redis."""
    if not redis_client:
        return False
    
    try:
        payload = json.dumps(value)
        effective_ttl = ttl_seconds or settings.CACHE_EXPIRATION_SECONDS
        # CAMBIO CLAVE: Usamos `await`
        await redis_client.set(key, payload, ex=effective_ttl)
        print(f"CACHE_SET (Generic): Valor guardado para la clave '{key}' con TTL {effective_ttl}s.")
        return True
    except Exception as e:
        print(f"CACHE_ERROR: Error en set_generic_cache_async para la clave '{key}': {e}")
        return False

async def get_generic_cache_async(redis_client: Optional[AsyncRedis], key: str) -> Optional[Any]:
    """(ASÍNCRONO) Obtiene un valor genérico de Redis."""
    if not redis_client:
        return None

    try:
        # CAMBIO CLAVE: Usamos `await`
        cached_value = await redis_client.get(key)
        if cached_value:
            # `decode_responses=True` en la conexión ya debería devolver un string,
            # pero por si acaso, decodificamos explícitamente si es bytes.
            value_str = cached_value.decode("utf-8") if isinstance(cached_value, bytes) else cached_value
            return json.loads(value_str)
    except json.JSONDecodeError:
        # Si no es un JSON válido, puede que hayamos guardado un string simple.
        return value_str
    except Exception as e:
        print(f"CACHE_ERROR: Error en get_generic_cache_async para la clave '{key}': {e}")
    return None

async def delete_generic_cache_async(redis_client: Optional[AsyncRedis], key: str) -> bool:
    """(ASÍNCRONO) Elimina una clave genérica de Redis."""
    if not redis_client:
        return False
    
    try:
        # CAMBIO CLAVE: Usamos `await`
        await redis_client.delete(key)
        print(f"CACHE_DELETE (Generic): Clave '{key}' eliminada.")
        return True
    except Exception as e:
        print(f"CACHE_ERROR: Error en delete_generic_cache_async para la clave '{key}': {e}")
        return False