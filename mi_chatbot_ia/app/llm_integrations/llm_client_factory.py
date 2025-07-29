# app/llm_integrations/llm_client_factory.py
from app.models.llm_model_config import LLMModelConfig, LLMProviderType
from .base_client import LLMClient
from .google_client import GoogleGeminiClient
#from .openai_client import OpenAIClient 
from .ollama_client import OllamaClient 
from .bedrock_client import BedrockClient # <-- ¡NUEVO IMPORT!
from .openai_client import OpenAIClient  # <-- ¡NUEVO IMPORT!
# Cuando agregues más, impórtalos aquí. Ej: from .openai_client import OpenAIClient

def get_llm_client(config: LLMModelConfig) -> LLMClient:
    """
    Factory Function.
    Toma una configuración de LLM desde la BD y devuelve la instancia
    del cliente correspondiente.
    
    Args:
        config (LLMModelConfig): El objeto SQLAlchemy que describe el modelo.

    Returns:
        LLMClient: Una instancia de un cliente específico (Google, OpenAI, etc.).
    
    Raises:
        NotImplementedError: Si el proveedor del modelo no tiene un cliente implementado.
    """
    provider_map = {
        LLMProviderType.GOOGLE: GoogleGeminiClient,
        LLMProviderType.OLLAMA: OllamaClient,
        LLMProviderType.BEDROCK: BedrockClient, # <-- ¡NUEVA LÍNEA MÁGICA!
        LLMProviderType.OPENAI: OpenAIClient, # <-- ¡NUEVA LÍNEA!

        # ===> AQUÍ ES DONDE AÑADIRÁS LOS OTROS PROVEEDORES EN EL FUTURO <===
        # LLMProviderType.OPENAI: OpenAIClient,
        # LLMProviderType.ANTHROPIC: AnthropicClient,
    }

    client_class = provider_map.get(config.provider)

    if client_class:
        print(f"LLM_FACTORY: Creando cliente para proveedor: {config.provider.value}")
        return client_class(config)
    else:
        print(f"ERROR: No hay implementación de cliente para el proveedor '{config.provider.value}'.")
        raise NotImplementedError(f"El cliente para el proveedor '{config.provider.value}' aún no está implementado.")