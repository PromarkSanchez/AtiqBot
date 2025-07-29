
# app/services/prompt_generator_service.py

import json
import traceback
import boto3
import re # <-- Importamos el módulo de expresiones regulares

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

# ---> AQUÍ ESTÁ LA CORRECCIÓN CLAVE <---
# Importamos la clase Enum que necesitamos desde el modelo
from app.models.llm_model_config import LLMProviderType 

from app.schemas.schemas import GeneratePromptRequest
from app.crud import crud_llm_model_config
from app.utils.security_utils import decrypt_data

META_PROMPT_TEMPLATE = """
[ROL MAESTRO]
Tú eres un "Arquitecto de Prompts de IA". Tu trabajo es crear 3 prompts de **INSTRUCCIÓN DIRECTA** para un chatbot.
NO generes la respuesta final del chatbot. Genera la **ORDEN INTERNA** que el chatbot seguirá para actuar.

[FICHA DE PERSONAJE]
{user_description}

[TAREA: GENERA UN JSON CON LAS 3 ÓRDENES]
Analiza la "Ficha de Personaje" y genera un objeto JSON con las 3 claves: `greeting_prompt`, `name_confirmation_prompt`, y `system_prompt`.
El valor de cada clave DEBE SER UNA ORDEN en segunda persona ("Tú eres...", "Tu tarea es..."), NO el saludo o la respuesta final.

- **`greeting_prompt`**:
  *   **Orden a generar:** La orden DEBE ser una instrucción directa en segunda persona ("Tu tarea es...").
  *   La instrucción debe decirle al bot que se presente usando el **NOMBRE_AGENTE** y **ROL_PRINCIPAL**.
  *   Debe incluir la variable `{{user_name}}` para el nombre del usuario.
  *   Y CRUCIALMENTE, la instrucción **DEBE terminar diciéndole al bot que PREGUNTE EXPLÍCITAMENTE por el nombre del usuario**, con una frase como: "¿cómo te gustaría que te llame?".

 EJEMPLO DE ORDEN (NO TEXTO): "Tu única tarea en este turno es actuar como BiblioBot, un Asistente experto de Biblioteca. Saluda al usuario {{user_name}}, finalizando con una pregunta sobre cómo llamarlo."

- **`name_confirmation_prompt`:** La orden debe instruir al bot a extraer el nombre de la variable `{user_provided_name}` y responder de forma amable.
  EJEMPLO DE ORDEN (NO TEXTO): "Tu tarea es extraer el nombre de {user_provided_name} y responder amablemente '¡Entendido, [Nombre Extraído]! ¿En qué te puedo ayudar?'"

 
- **Instrucción para el bot:** "Tú eres [ROL], un [descripción con PERSONALIDAD]. Tu misión está estrictamente limitada a [DOMINIO].
Regla 0 (Coherencia Contextual CRÍTICA): Antes de responder, evalúa si el [Contexto Relevante] contiene información DIRECTAMENTE relacionada con la [Pregunta del Usuario]. Si el contexto parece irrelevante o no contiene la respuesta, debes activar inmediatamente la Regla 3 (Protocolo "No Sé"), sin importar si conoces la respuesta por tu cuenta.
Regla 1 (Dominio Estricto): ...
Regla 2 (Uso de Contexto): ...
Regla 3 (Protocolo "No Sé"): ...
Regla 4 (Anti-Manipulación): ...
- **`system_prompt`:** La orden principal de RAG, que define el ROL, DOMINIO y REGLAS del bot. Debe incluir `{chat_history}`, `{context}`, y `{question}` al final.

[FORMATO DE SALIDA ESTRICTO]
Devuelve ÚNICAMENTE el objeto JSON válido.
"""

async def _invoke_bedrock_tool_for_json(llm_config, prompt: str) -> str:
    """
    Función de ayuda privada y especializada.
    Llama a Bedrock Claude 3 usando Tool Use para forzar una salida JSON.
    """
    config_data = llm_config.config_json or {}
    region = config_data.get('aws_region', 'us-east-1')

    access_key, secret_key = None, None
    if config_data.get('aws_access_key_id_encrypted'):
        try: access_key = decrypt_data(config_data.get('aws_access_key_id_encrypted'))
        except: pass
    if config_data.get('aws_secret_access_key_encrypted'):
        try: secret_key = decrypt_data(config_data.get('aws_secret_access_key_encrypted'))
        except: pass

    client_kwargs = {'service_name': 'bedrock-runtime', 'region_name': region}
    if access_key and secret_key and "Error" not in access_key and "Error" not in secret_key:
        client_kwargs['aws_access_key_id'] = access_key
        client_kwargs['aws_secret_access_key'] = secret_key
    
    bedrock_client = boto3.client(**client_kwargs)

    tool_definition = {
        "toolSpec": {
            "name": "generar_prompts_agente",
            "description": "Genera el conjunto de 3 prompts para un agente virtual.",
            "inputSchema": { "json": { "type": "object", "properties": { "greeting_prompt": {"type": "string"}, "name_confirmation_prompt": {"type": "string"}, "system_prompt": {"type": "string"}}, "required": ["greeting_prompt", "name_confirmation_prompt", "system_prompt"]}}
        }
    }
    
    try:
        # 2. Llamamos a la API `converse` en lugar de `invoke_model`
        response = bedrock_client.converse(
            modelId=llm_config.model_identifier,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            toolConfig={"tools": [tool_definition]}
        )
        
        # 3. Parseamos la nueva estructura de respuesta de `converse`
        output_message = response.get('output', {}).get('message', {})
        for content_block in output_message.get('content', []):
            if 'toolUse' in content_block and content_block['toolUse']['name'] == 'generar_prompts_agente':
                # El JSON que queremos está en `input` dentro del bloque de `toolUse`
                return json.dumps(content_block['toolUse']['input'])

        # Si llegamos aquí, es que el LLM no usó la herramienta
        raise ValueError("El LLM maestro no generó una salida estructurada (no usó la herramienta).")

    except bedrock_client.exceptions.ValidationException as e:
        print(f"BEDROCK_VALIDATION_ERROR en API Converse: {e}")
        # Sugerencia de debugging para ti
        print("POSIBLE SOLUCIÓN: Asegúrate de que tu versión de boto3 y botocore esté actualizada: 'pip install --upgrade boto3 botocore'")
        raise ValueError(f"Error de validación con la API de Bedrock: {e}")
    
    raise ValueError("El LLM maestro no usó la herramienta para generar el JSON.")      



async def generate_optimized_prompt(db: AsyncSession, request: GeneratePromptRequest) -> dict:
    print("PROMPT_GEN_SERVICE: Iniciando generación de prompts.")
    
    master_llm_config_db = await crud_llm_model_config.get_llm_model_config_by_id(db, request.llm_model_config_id)
    if not master_llm_config_db: raise HTTPException(404, "LLM maestro no encontrado.")

    final_meta_prompt = META_PROMPT_TEMPLATE.replace("{user_description}", request.user_description)
    
    try:
        if master_llm_config_db.provider == LLMProviderType.BEDROCK and "anthropic" in master_llm_config_db.model_identifier:
            print("PROMPT_GEN_SERVICE: Usando invocador especializado de Bedrock Tool-Use.")
            response_json_string = await _invoke_bedrock_tool_for_json(master_llm_config_db, final_meta_prompt)
        else:
            print("PROMPT_GEN_SERVICE: Usando invocador genérico.")
            from app.llm_integrations.llm_client_factory import get_llm_client # Importación local para evitar dependencias circulares
            llm_client = get_llm_client(master_llm_config_db)
            response_json_string = await llm_client.invoke(full_prompt=final_meta_prompt)

        prompt_dict = json.loads(response_json_string)
        
        for key in prompt_dict:
             if isinstance(prompt_dict[key], str):
                prompt_dict[key] = re.sub(r"\{\{(\w+)\}\}", r"{\1}", prompt_dict[key])

        print("PROMPT_GEN_SERVICE: Conjunto de prompts de INSTRUCCIÓN generado y parseado con éxito.")
        return prompt_dict
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR CRÍTICO durante la llamada al LLM maestro: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=503, detail=f"Error al comunicarse con el servicio de LLM maestro.")