# app/llm_integrations/openai_client.py

import openai
from .base_client import LLMClient
from app.models.llm_model_config import LLMModelConfig
from app.utils.security_utils import decrypt_data

class OpenAIClient(LLMClient):
    """
    Implementación específica del cliente LLM para los modelos de OpenAI (GPT).
    """
    def __init__(self, config: LLMModelConfig):
        super().__init__(config)
        
        if not self.config.api_key_encrypted:
            raise ValueError(f"No se encontró una API Key encriptada para el modelo OpenAI '{self.config.display_name}'.")
        
        try:
            self.api_key = decrypt_data(self.config.api_key_encrypted)
        except Exception as e:
            raise ValueError(f"Fallo al desencriptar la API key para '{self.config.display_name}': {e}")
            
        try:
            # La inicialización del cliente de OpenAI es un poco diferente
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            print(f"OPENAI_CLIENT: Cliente para GPT '{self.model_name}' configurado correctamente.")
        except Exception as e:
            print(f"ERROR: Falló la configuración del SDK de OpenAI: {e}")
            raise e

    async def invoke(self, full_prompt: str) -> str:
        """Llama a la API de OpenAI para generar una respuesta."""
        print(f"OPENAI_CLIENT: Invocando modelo '{self.model_name}'...")
        try:
            # OpenAI distingue claramente entre system y user prompt
            # Aquí necesitaríamos adaptar la entrada, pero para un prompt simple sería así:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": full_prompt}]
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"ERROR: Ocurrió un error al invocar la API de OpenAI: {e}")
            raise e