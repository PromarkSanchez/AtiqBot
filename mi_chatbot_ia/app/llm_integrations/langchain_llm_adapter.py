# app/llm_integrations/langchain_llm_adapter.py (Versión FINAL que obedece)
import os
import json
import boto3

# --- LangChain Imports ---
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from langchain_aws import ChatBedrock
from langchain_openai import ChatOpenAI

# --- Local Imports ---
from app.models.llm_model_config import LLMModelConfig, LLMProviderType
from app.utils.security_utils import decrypt_data

def get_langchain_llm_adapter(config: LLMModelConfig, temperature_to_use: float) -> BaseChatModel:
    """
    Crea y devuelve una instancia de LangChain usando la configuración y la TEMPERATURA EXACTA
    proporcionada. Ya no toma decisiones, solo construye.
    """
    provider = config.provider
    print(f"LANGCHAIN_ADAPTER: Construyendo '{config.display_name}' con Temp: {temperature_to_use:.2f}")

    # --- Desencriptado de API Key ---
    api_key = None
    if config.api_key_encrypted:
        try:
            api_key = decrypt_data(config.api_key_encrypted)
        except Exception as e:
            raise ValueError(f"Fallo al desencriptar API key para '{config.display_name}'. Error: {e}")

    # --- Parámetros de Modelo ---
    model_identifier = config.model_identifier.strip()
    max_tokens = config.default_max_tokens # No necesitamos overrides aquí

    # ==========================================================
    # ======>        CONSTRUCCIÓN POR PROVEEDOR            <======
    # ==========================================================
    
    if provider == LLMProviderType.OLLAMA:
        base_url = config.base_url or "http://localhost:11434"
        print(f"LANGCHAIN_ADAPTER: Target Ollama: '{base_url}', Modelo: '{model_identifier}'")
        return ChatOllama(base_url=base_url, model=model_identifier, temperature=temperature_to_use)

    elif provider == LLMProviderType.GOOGLE:
        if not api_key: raise ValueError("Proveedor Google requiere una API Key.")
        gemini_params = {"model": model_identifier, "google_api_key": api_key, "temperature": temperature_to_use}
        if max_tokens: gemini_params["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**gemini_params)

    elif provider == LLMProviderType.BEDROCK:
        config_data = json.loads(config.config_json) if isinstance(config.config_json, str) else (config.config_json or {})
        aws_region = config_data.get('aws_region', os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
        
        boto3_client_kwargs = {'region_name': aws_region}
        access_key = decrypt_data(config_data.get('aws_access_key_id_encrypted', ''))
        secret_key = decrypt_data(config_data.get('aws_secret_access_key_encrypted', ''))

        if access_key and secret_key:
            print("LANGCHAIN_ADAPTER: Usando credenciales de Bedrock explícitas.")
            boto3_client_kwargs.update({'aws_access_key_id': access_key, 'aws_secret_access_key': secret_key})
        
        bedrock_client = boto3.client('bedrock-runtime', **boto3_client_kwargs)
        
        model_kwargs = {"temperature": temperature_to_use}
        if max_tokens:
            if "anthropic" in model_identifier: model_kwargs["max_tokens"] = max_tokens
            elif "meta" in model_identifier: model_kwargs["max_gen_len"] = max_tokens
            elif "cohere" in model_identifier: model_kwargs["max_tokens"] = max_tokens
        
        return ChatBedrock(client=bedrock_client, model_id=model_identifier, model_kwargs=model_kwargs)
        
    elif provider == LLMProviderType.OPENAI:
        if not api_key: raise ValueError("Proveedor OpenAI requiere una API Key.")
        openai_params = {"model": model_identifier, "temperature": temperature_to_use, "api_key": api_key}
        if max_tokens: openai_params["max_tokens"] = max_tokens
        if config.base_url: openai_params["base_url"] = config.base_url
        return ChatOpenAI(**openai_params)
        
    else:
        raise NotImplementedError(f"El adaptador para '{provider.value}' no está implementado.")