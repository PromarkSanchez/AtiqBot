select * from virtual_agent_profiles
"[INST]
**System:** Tu nombre Hered-IA, y eres un asistente virtual amigable de la Universidad Peruana Cayetano Heredia. Sigue las siguientes reglas de forma estricta y sin excepciones.

**REGLAS FUNDAMENTALES:**

1.  **Dependencia Absoluta del Contexto:** Tu ÚNICA fuente de información es el texto en la sección ""Contexto Relevante"". Tienes ESTRICTAMENTE PROHIBIDO usar tu conocimiento general o hacer cálculos. Tu única función es buscar y reformular la información del contexto.

2.  **Protocolo Obligatorio para Contexto Vacío:** Si la sección ""Contexto Relevante"" está vacía o no contiene la respuesta a la ""Pregunta del Usuario"", tu ÚNICA y OBLIGATORIA respuesta debe ser la frase exacta: ""No tengo información sobre lo que consultas."" NO intentes responder la pregunta de otra forma.

**EJEMPLO DE CÓMO APLICAR LAS REGLAS:**

*   **SI el contexto está vacío y el usuario pregunta ""cuánto es 2+2"":**
    *   **Tu Respuesta CORRECTA:** ""No tengo información sobre lo que consultas.""
    *   **Tu Respuesta INCORRECTA:** ""4""

**Contexto Relevante:**
{context}

**Pregunta del Usuario:**
{question}
[/INST]
**Respuesta:**"

select * from chat_message_history_v2 order by 1 desc
TRUNCATE TABLE chat_message_history_v2 RESTART IDENTITY CASCADE;


select * from llm_model_configs
"gAAAAABod9EBRXny-Fa-pbK6Y7yWJ21BVwbbBWm4kBM7n4LdXVNXZKRePZvIDGA-5_gpIAxfhFmSDyChYZf0HBxslwzT1SooAcTwuAlRYR6kVzpSONaXW7hs18pwjrntGqi11ZJrn6TL"
"gAAAAABod9JXd9e0HfMZ7gzRLdM6qL53nywVQSuioPxOj304Lg7UcBFk_cu2ZWBw7mLfoAylZPHj5qSGwnO1GnpkBpjtPm3wJZyallee1n0uv2ZQUIRSKLiZpOhXtKooDGFPOXgTtdKq"


select  * from context_definitions
select * from virtual_agent_profiles

SELECT id, name FROM virtual_agent_profiles;
select * from api_clients

"{""application_id"": ""WEB_BB_UPCH"", ""allowed_context_ids"": [2], ""is_web_client"": false, ""allowed_web_origins"": [], ""human_handoff_agent_group_id"": null, ""default_llm_model_config_id_override"": 5, ""default_virtual_agent_profile_id_override"": 7, ""history_k_messages"": 3, ""max_tokens_per_response_override"": null}"

contex






ALTER TABLE virtual_agent_profiles
ADD COLUMN greeting_prompt TEXT;

ALTER TABLE virtual_agent_profiles
ADD COLUMN name_confirmation_prompt TEXT;

COMMENT ON COLUMN virtual_agent_profiles.greeting_prompt IS 'Prompt para la ETAPA 1: Saludo inicial.';
COMMENT ON COLUMN virtual_agent_profiles.name_confirmation_prompt IS 'Prompt para la ETAPA 2: Confirmación de nombre.';



UPDATE virtual_agent_profiles
SET 
    greeting_prompt = 'Tu tarea es iniciar la conversación. Preséntate como "Hered-IA", el tutor de IA para el curso de Matemática Básica de la UPCH. Saluda amablemente y pregunta por el nombre del usuario para personalizar la interacción. Usa un emoticón 👋.

Ejemplo de saludo: "¡Hola! Soy Hered-IA, tu tutor de IA para Matemáticas Básicas aquí en Cayetano. 👋 Para empezar, ¿cómo te llamas?"',
    name_confirmation_prompt = 'La frase del usuario es: ""{user_input}"". Extrae solo el nombre propio de la frase. Luego, responde usando esta plantilla exacta: ""¡Mucho gusto, [NOMBRE EXTRAIDO]! 😊 ¿En qué puedo ayudarte hoy con el curso de Matemática Básica, los anuncios o tus tareas?"".'
WHERE
    id = 13; -- <-- ¡ASEGÚRATE DE QUE ESTE ID SEA EL CORRECTO!


SELECT 
    id, 
    name, 
    greeting_prompt, 
    name_confirmation_prompt, 
    system_prompt
FROM 
    virtual_agent_profiles 
WHERE 
    id = 7;

SELECT unnest(enum_range(NULL::llm_provider_type_enum));

SELECT unnest(enum_range(NULL::llm_model_type_enum));
ALTER TYPE llm_provider_type_enum ADD VALUE 'BEDROCK';


 
INSERT INTO public.llm_model_configs (
    model_identifier, 
    display_name, 
    provider, 
    model_type, 
    is_active, 
    base_url,
    default_temperature, 
    default_max_tokens, 
    supports_system_prompt, 
    config_json, 
    api_key_encrypted
) VALUES (
    'anthropic.claude-3',   
    'Claude 3 Haiku',        
    'BEDROCK',                                     
    'CHAT_COMPLETION',                            
    TRUE,                                         
    NULL,                                          
    0.7,                                          
    4096,                                          
    TRUE,                                          
    '{"aws_region": "us-east-1"}',                 
    NULL                                           
);


select * from public.llm_model_configs order by 1





