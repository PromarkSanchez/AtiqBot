# app/llm_integrations/google_client.py

import google.generativeai as genai
from .base_client import LLMClient
from app.models.llm_model_config import LLMModelConfig
from app.utils.security_utils import decrypt_data as decrypt_value  


class GoogleGeminiClient(LLMClient):
    """
    Implementación específica del cliente LLM para Google Gemini.
    Ahora obtiene la API key desencriptada.
    """
    def __init__(self, config: LLMModelConfig):
        super().__init__(config)
        
        # [REFACTOR] Obtiene la clave desencriptada desde el config.
        if not self.config.api_key_encrypted:
            raise ValueError(f"No se encontró una API Key encriptada para el modelo '{self.config.display_name}'.")
        
        try:
            self.api_key = decrypt_value(self.config.api_key_encrypted)
        except Exception as e:
            raise ValueError(f"Fallo al desencriptar la API key para '{self.config.display_name}': {e}")
            
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            print(f"GOOGLE_CLIENT: Cliente para Gemini '{self.model_name}' configurado correctamente.")
        except Exception as e:
            print(f"ERROR: Falló la configuración del SDK de Google Gemini: {e}")
            raise e

    # La firma de invoke ahora debe ser más simple para este cliente no-langchain
    async def invoke(self, full_prompt: str) -> str:
        """Llama a la API de Google Gemini para generar contenido."""
        print(f"GOOGLE_CLIENT: Invocando modelo '{self.model_name}' con prompt...")
        try:
            response = await self.model.generate_content_async(full_prompt)
            if not response.parts:
                print("WARNING: La respuesta de Gemini no contiene 'parts'.")
                return response.text
            return response.text.strip()
        except Exception as e:
            print(f"ERROR: Ocurrió un error al invocar la API de Gemini: {e}")
            raise e