# app/llm_integrations/langchain_llm_adapter.py
import os
from app.models.llm_model_config import LLMModelConfig, LLMProviderType
from app.utils.security_utils import decrypt_data # <--- Importamos tu decrypt_data

# LangChain Imports
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from langchain_aws import ChatBedrock
from langchain_openai import ChatOpenAI

def get_langchain_llm_adapter(config: LLMModelConfig) -> BaseChatModel:
    provider = config.provider
    print(f"LANGCHAIN_ADAPTER: Creando adaptador para '{config.display_name}'.")

    # [REFACTOR-FINAL] Desencriptar la API key desde la BD
    api_key = None
    if config.api_key_encrypted:
        try:
            print(f"LANGCHAIN_ADAPTER: Desencriptando API key para el modelo...")
            api_key = decrypt_data(config.api_key_encrypted)
        except Exception as e:
            raise ValueError(f"No se pudo desencriptar la API key para el modelo '{config.display_name}'. Error: {e}")
            
    # La lógica para comprobar si la clave es necesaria para ciertos proveedores.
    if not api_key:
        if config.provider in [LLMProviderType.GOOGLE, LLMProviderType.OPENAI, LLMProviderType.ANTHROPIC, LLMProviderType.AZURE_OPENAI,LLMProviderType.BEDROCK]:
            raise ValueError(f"El modelo '{config.display_name}' de tipo '{config.provider}' requiere una API Key, pero no se encontró una configurada o desencriptable.")

    clean_model_identifier = config.model_identifier.replace("models/", "")
    
    common_params = {
        "model_name": clean_model_identifier, 
        "temperature": config.default_temperature if config.default_temperature is not None else 0.7,
    }

    if provider == LLMProviderType.GOOGLE:
        return ChatGoogleGenerativeAI(
            model=common_params["model_name"],
            google_api_key=api_key, # <--- Pasamos la clave desencriptada
            temperature=common_params["temperature"],
        )
    elif provider == LLMProviderType.OLLAMA:
        print(f"LANGCHAIN_ADAPTER: Creando adaptador para Ollama, modelo '{config.model_identifier}'")
        
        return ChatOllama(
            base_url=config.base_url or "http://localhost:11434",
            model=config.model_identifier,
            temperature=config.default_temperature if config.default_temperature is not None else 0.7,
            # Se pueden añadir más opciones aquí si es necesario
        )
    elif provider == LLMProviderType.BEDROCK:
        print(f"LANGCHAIN_ADAPTER: Creando adaptador de Bedrock para '{config.display_name}'.")
        # Para Bedrock, no necesitamos una API key.
        # Las credenciales se obtienen del entorno (Rol IAM es lo ideal).
        
        # Creamos los kwargs específicos para este modelo
        model_kwargs = {
            # Aquí podrías poner kwargs específicos para el modelo, ej: "max_tokens_to_sample" para Claude v2
            "temperature": config.default_temperature if config.default_temperature is not None else 0.7,
        }

        # La región puede venir del config o de una variable de entorno
        aws_region = getattr(config, 'aws_region', os.environ.get('AWS_REGION', 'us-east-1'))

        # Creamos el cliente de boto3 aquí mismo
        boto3_bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
        )

        return ChatBedrock(
            client=boto3_bedrock_client,
            model_id=config.model_identifier, # <-- ¡Usa el ID oficial de Bedrock!
            model_kwargs=model_kwargs,
        )
    else:
        raise NotImplementedError(f"El adaptador de LangChain para el proveedor '{provider.value}' aún no está implementado.")