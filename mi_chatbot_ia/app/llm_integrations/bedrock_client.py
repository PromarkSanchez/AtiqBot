# app/llm_integrations/bedrock_client.py

import boto3
import json
from .base_client import LLMClient
from app.models.llm_model_config import LLMModelConfig
from app.utils.security_utils import decrypt_data

class BedrockClient(LLMClient):
    """
    Cliente Bedrock que lee credenciales explícitas desde config_json.
    Ahora maneja el caso de que config_json se lea como un string.
    """
    def __init__(self, config: LLMModelConfig):
        super().__init__(config)

        # --> INICIO DE LA CORRECCIÓN <--
        config_data = {}
        if self.config.config_json:
            # Si config_json es un string, lo convertimos a un diccionario.
            # Si ya es un diccionario, esta línea no hace daño.
            if isinstance(self.config.config_json, str):
                try:
                    config_data = json.loads(self.config.config_json)
                except json.JSONDecodeError:
                    print(f"BEDROCK_CLIENT_WARNING: No se pudo decodificar el string de config_json para el modelo '{self.config.display_name}'.")
                    config_data = {}
            # Si es un diccionario (el caso ideal), simplemente lo usamos.
            elif isinstance(self.config.config_json, dict):
                config_data = self.config.config_json
        
        # El resto del código ahora puede confiar en que config_data es un diccionario.
        self.aws_region = config_data.get('aws_region', 'us-east-1')

        access_key = None
        # Usamos .get() que devuelve None si la clave no existe, más seguro
        if config_data.get('aws_access_key_id_encrypted'):
            try:
                decrypted_key = decrypt_data(config_data['aws_access_key_id_encrypted'])
                # La función de desencriptación devuelve un string de error específico, lo verificamos
                if "ERROR DE DESENCRIPTACIÓN" not in decrypted_key:
                    access_key = decrypted_key
                else:
                    print("BEDROCK_CLIENT_ERROR: La clave aws_access_key_id_encrypted parece corrupta o inválida.")
            except Exception as e:
                print(f"BEDROCK_CLIENT_ERROR: Excepción al desencriptar aws_access_key_id_encrypted: {e}")

        secret_key = None
        if config_data.get('aws_secret_access_key_encrypted'):
            try:
                decrypted_secret = decrypt_data(config_data['aws_secret_access_key_encrypted'])
                if "ERROR DE DESENCRIPTACIÓN" not in decrypted_secret:
                    secret_key = decrypted_secret
                else:
                    print("BEDROCK_CLIENT_ERROR: La clave aws_secret_access_key_encrypted parece corrupta o inválida.")
            except Exception as e:
                print(f"BEDROCK_CLIENT_ERROR: Excepción al desencriptar aws_secret_access_key_encrypted: {e}")

        # El resto del __init__ no cambia, ya que su lógica es correcta.
        client_kwargs = { 'service_name': 'bedrock-runtime', 'region_name': self.aws_region }
        if access_key and secret_key:
            print("BEDROCK_CLIENT: Usando credenciales explícitas de config_json.")
            client_kwargs['aws_access_key_id'] = access_key
            client_kwargs['aws_secret_access_key'] = secret_key
        else:
            print("BEDROCK_CLIENT: Usando credenciales de entorno.")
        
        try:
            self.client = boto3.client(**client_kwargs)
            print(f"BEDROCK_CLIENT: Cliente inicializado.")
        except Exception as e:
            print(f"BEDROCK_CLIENT_ERROR: Fallo al crear el cliente. Error: {e}")
            raise

    async def invoke(self, full_prompt: str) -> str:
        body, accept, contentType = self._prepare_request(full_prompt)
        try:
            # ### [MEJORA] ### Usar invoke_model_with_response_stream sería aún mejor para el futuro, pero invoke_model es más simple por ahora.
            response = self.client.invoke_model(
                body=body,
                modelId=self.model_name, # Aquí va 'anthropic.claude-3-haiku-20240307-v1:0'
                accept=accept,
                contentType=contentType
            )
            return self._parse_response(response)
        except Exception as e:
            print(f"Error invocando el modelo de Bedrock {self.model_name}: {e}")
            raise

    def _prepare_request(self, prompt: str):
        """Prepara el 'body' y headers correctos según la familia del modelo."""
        # ### [MEJORA] ### Hacemos esto más robusto y configurable.
        if "anthropic" in self.model_name:
            body = {
                # Esta versión funciona tanto para Claude 2 como para Claude 3
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.config.default_max_tokens or 4096,
                "temperature": self.config.default_temperature if self.config.default_temperature is not None else 0.7,
                "messages": [{"role": "user", "content": prompt}]
            }
        # Otros modelos pueden tener un formato diferente
        elif "cohere" in self.model_name:
            body = {
                "prompt": prompt,
                "max_tokens": self.config.default_max_tokens or 4096,
                "temperature": self.config.default_temperature if self.config.default_temperature is not None else 0.7
            }
        elif "meta" in self.model_name: # Llama 2/3
            body = {
                "prompt": f"[INST] {prompt} [/INST]",
                "max_gen_len": self.config.default_max_tokens or 2048,
                "temperature": self.config.default_temperature if self.config.default_temperature is not None else 0.7
            }
        else:
            raise NotImplementedError(f"El formato del body para la familia '{self.model_name}' no está implementado.")
        
        return json.dumps(body), 'application/json', 'application/json'

    def _parse_response(self, response) -> str:
        """Parsea el stream de bytes de la respuesta según el proveedor."""
        response_body = json.loads(response.get('body').read())
        # ### [MEJORA] ### La respuesta de Claude 3 es igual que la de Claude 2.1 en este aspecto
        if "anthropic" in self.model_name:
            # Buscamos en el contenido el bloque de texto
            for block in response_body.get('content', []):
                if block.get('type') == 'text':
                    return block.get('text', '')
            return "" # Devolvemos vacío si no hay texto
        elif "cohere" in self.model_name:
            return response_body['generations'][0]['text']
        elif "meta" in self.model_name:
            return response_body.get('generation', '')
        else:
            raise NotImplementedError(f"El parser de respuesta para '{self.model_name}' no está implementado.")