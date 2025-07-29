# app/core/app_state.py
from sentence_transformers import SentenceTransformer # type: ignore

# Esta variable será el singleton de nuestro modelo
embedding_model_chat_instance: SentenceTransformer = None # type: ignore
MODEL_NAME_FOR_EMBEDDING_CHAT = 'all-MiniLM-L6-v2'

def get_embedding_model_chat() -> SentenceTransformer:
    """
    Retorna la instancia del modelo de embedding, cargándola si es necesario.
    """
    global embedding_model_chat_instance
    if embedding_model_chat_instance is None:
        print(f"APP_STATE: Cargando modelo de embedding por primera vez: {MODEL_NAME_FOR_EMBEDDING_CHAT}...")
        try:
            embedding_model_chat_instance = SentenceTransformer(MODEL_NAME_FOR_EMBEDDING_CHAT)
            print("APP_STATE: Modelo de embedding cargado EXITOSAMENTE.")
        except Exception as e:
            print(f"ERROR CRÍTICO en APP_STATE: No se pudo cargar el modelo de embedding: {e}")
            # Aquí podrías decidir si la aplicación debe fallar o continuar
            # sin el modelo (lo cual probablemente no sea útil).
            # raise RuntimeError(f"Fallo al cargar el modelo de embedding: {e}") # Opción para detener la app
            return None # O retornar None y manejarlo en los endpoints
    return embedding_model_chat_instance