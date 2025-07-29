# app/llm_integrations/base_client.py
from abc import ABC, abstractmethod
from app.models.llm_model_config import LLMModelConfig

class LLMClient(ABC):
    """
    Clase Base Abstracta (Interfaz) para clientes de LLM no-langchain.
    """
    def __init__(self, config: LLMModelConfig):
        self.config = config
        self.model_name = config.model_identifier.replace("models/", "") # Limpiamos el nombre
        print(f"BASE_CLIENT: Inicializando cliente para '{self.config.display_name}' (Proveedor: {self.config.provider.value})")

    @abstractmethod
    async def invoke(self, full_prompt: str) -> str:
        """
        Método principal para interactuar con el LLM.
        """
        pass