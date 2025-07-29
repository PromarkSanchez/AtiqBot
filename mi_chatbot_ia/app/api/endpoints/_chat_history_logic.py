# app/api/endpoints/_chat_history_logic.py (Versión ASÍNCRONA Final con Redis)

import json
from typing import List, Optional

# Ya no importamos nada de SQLAlchemy aquí.
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, message_to_dict
from redis.asyncio import Redis as AsyncRedis

class FullyCustomChatMessageHistory(BaseChatMessageHistory):
    """
    Historial de chat ASÍNCRONO basado en Redis para alto rendimiento.
    Esta clase reemplaza por completo la versión antigua basada en SQLAlchemy.
    """
    def __init__(self, session_id: str, redis_client: Optional[AsyncRedis], ttl_seconds: int = 3600):
        # Ahora requiere un cliente de Redis asíncrono para funcionar.
        if not redis_client:
            # Si Redis no está disponible, el historial funcionará en memoria solo para esta petición.
            self.redis_client = None 
            self._messages: List[BaseMessage] = []
            print("WARNING: Redis client no disponible para historial. Usando memoria temporal.")
        else:
            self.redis_client = redis_client

        self.session_id = session_id
        self.key = f"message_store:{self.session_id}"
        self.ttl = ttl_seconds

    @property
    async def messages(self) -> List[BaseMessage]:
        """Propiedad desaconsejada. Usar get_messages_async en su lugar."""
        return await self.get_messages_async()
        
    async def get_messages_async(self) -> List[BaseMessage]:
        """Obtiene los mensajes de forma asíncrona desde Redis."""
        if not self.redis_client:
            return self._messages

        _items = await self.redis_client.lrange(self.key, 0, -1)
        items = [json.loads(m) for m in _items] # El cliente con decode_responses=True ya devuelve strings
        messages = messages_from_dict(items)
        return messages

    async def add_messages(self, messages: List[BaseMessage]) -> None:
        """Método desaconsejado. Usar add_messages_async en su lugar."""
        await self.add_messages_async(messages)
        
    async def add_messages_async(self, messages: List[BaseMessage]) -> None:
        """Añade mensajes de forma asíncrona a la lista de Redis."""
        if not self.redis_client:
            self._messages.extend(messages)
            return

        async with self.redis_client.pipeline() as pipe:
            for message in messages:
                pipe.rpush(self.key, json.dumps(message_to_dict(message)))
            if self.ttl:
                pipe.expire(self.key, self.ttl)
            await pipe.execute()

    async def clear_async(self) -> None:
        """Limpia el historial de forma asíncrona."""
        if not self.redis_client:
            self._messages = []
            return
        await self.redis_client.delete(self.key)

    def clear(self) -> None:
        """Limpia el historial. En un entorno async, esto puede ser problemático."""
        if not self.redis_client:
            self._messages = []
            return
        # Esta es una llamada síncrona que podría bloquear. Es mejor usar clear_async.
        try:
            # Intenta obtener el loop de eventos existente para correr la corutina
            loop = asyncio.get_running_loop()
            loop.create_task(self.clear_async())
        except RuntimeError:
             # Si no hay un loop corriendo, no se puede hacer mucho.
             print("WARNING: El método clear() fue llamado en un contexto no-asíncrono.")

# Las otras clases y funciones que tenías (ContextAware, handoff) pueden ser añadidas debajo
# si aún las necesitas, pero asegúrate de que no usen la lógica síncrona antigua.