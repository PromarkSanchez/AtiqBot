# app/llm_integrations/ollama_client.py

from httpx import AsyncClient, Timeout
import json

from .base_client import LLMClient
from app.models.llm_model_config import LLMModelConfig

class OllamaClient(LLMClient):
    """
    Implementación específica del cliente para interactuar con modelos
    servidos a través de la API de Ollama.
    """
    def __init__(self, config: LLMModelConfig):
        super().__init__(config)
        
        # Para Ollama, la clave no es necesaria, pero la URL base sí.
        self.base_url = config.base_url or "http://localhost:11434"
        print(f"OLLAMA_CLIENT: Configurado para usar el endpoint: {self.base_url}")
        
        # Usamos httpx para hacer llamadas asíncronas a la API REST.
        self.client = AsyncClient(base_url=self.base_url, timeout=Timeout(300.0))

    async def invoke(self, full_prompt: str) -> str:
        """Llama al endpoint /api/generate de Ollama."""
        print(f"OLLAMA_CLIENT: Invocando modelo '{self.model_name}' en {self.base_url}...")
        
        # El payload que espera la API de Ollama
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False, # Queremos la respuesta completa, no un stream.
            "options": {
                "temperature": self.config.default_temperature or 0.7
            }
        }
        
        try:
            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status() # Lanza un error si el status es 4xx o 5xx
            
            response_data = response.json()
            return response_data.get("response", "").strip()
            
        except Exception as e:
            print(f"ERROR: Ocurrió un error al invocar la API de Ollama: {e}")
            raise e
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Asegura que el cliente httpx se cierre correctamente."""
        await self.client.aclose()