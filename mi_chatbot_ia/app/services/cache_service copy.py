# app/services/cache_service.py

import json
import hashlib
from typing import Optional, Dict, Any, List

from app.config import settings
from app.core.app_state import get_redis_client

# Esta es la función clave que crea la clave segura. La definimos aquí para ser reutilizada.
def _create_secure_cache_key(api_client_id: int, context_ids: List[int], question: str) -> str:
    """Crea una clave de caché segura que considera el perímetro de datos del usuario."""
    # Normalizamos el orden de los contextos para que [1, 2] y [2, 1] generen la misma clave.
    sorted_contexts = sorted(list(set(context_ids)))
    
    # Creamos el material para el hash.
    key_material = f"{api_client_id}:{','.join(map(str, sorted_contexts))}:{question.lower().strip()}"
    
    # Devolvemos un hash para una clave limpia y de longitud fija.
    return f"chatbot:v3:{hashlib.sha256(key_material.encode()).hexdigest()}"


# --- ¡AQUÍ ESTÁ EL CAMBIO IMPORTANTE! ---
# La firma de la función ahora coincide con cómo la llamamos.
def get_cached_response(api_client_id: int, context_ids: List[int], question: str) -> Optional[Dict[str, Any]]:
    """
    Recupera una respuesta cacheada como un diccionario Python.
    Ahora usa una clave segura que incluye los permisos.
    """
    redis_client = get_redis_client()
    if not redis_client:
        return None  # La caché está desactivada, no hacer nada.

    cache_key = _create_secure_cache_key(api_client_id, context_ids, question)
    
    try:
        cached_json = redis_client.get(cache_key)
        if cached_json:
            print(f"CACHE_HIT: Respuesta encontrada para la clave segura '{cache_key}'")
            return json.loads(cached_json)
    except Exception as e:
        print(f"CACHE_ERROR: Error al leer de Redis: {e}")

    return None


# --- ¡Y EL CAMBIO EN set_cached_response TAMBIÉN! ---
def set_cached_response(api_client_id: int, context_ids: List[int], question: str, response_dict: Dict[str, Any]):
    """
    Guarda un diccionario de respuesta en la caché de Redis usando una clave segura.
    """
    redis_client = get_redis_client()
    if not redis_client:
        return

    # No guardar respuestas vacías o de error
    bot_response_text = response_dict.get("bot_response", "")
    if not bot_response_text or "[Error" in bot_response_text:
        print("CACHE_SKIP: Respuesta inválida, no se guardará en caché.")
        return

    cache_key = _create_secure_cache_key(api_client_id, context_ids, question)
    
    try:
        json_value = json.dumps(response_dict)
        redis_client.set(cache_key, json_value, ex=settings.CACHE_EXPIRATION_SECONDS)
        print(f"CACHE_SET: Respuesta guardada en caché para la clave segura '{cache_key}'")
    except Exception as e:
        print(f"CACHE_ERROR: Error al escribir en Redis: {e}")