SELECT id, name, main_type, is_active, processing_config 
FROM context_definitions;

SELECT ctx.name AS context_name, doc.name AS document_source_name
FROM context_definitions ctx
JOIN context_document_source_assoc cda ON ctx.id = cda.context_definition_id
JOIN document_source_configs doc ON cda.document_source_config_id = doc.id
WHERE ctx.name = 'Contexto General Estudiantil';

SELECT * FROM chat_message_history_v2 ORDER BY id DESC LIMIT 10;

-- En chatbot_db
DROP TABLE IF EXISTS interaction_logs;

select * from interaction_logs


SELECT processing_config 
FROM context_definitions 
WHERE id = 2; -- O el ID de tu contexto "Esquema Data Warehouse Principal"


SELECT *,processing_config
FROM context_definitions 
WHERE id = 2; 
SELECT * FROM  public.api_clients
UPDATE public.api_clients 
SET settings ='"{""allowed_context_names"": [""Contexto General Estudiantil"", ""Esquema Data Warehouse Principal (con Políticas SQL)""]}"'
where id=1
SELECT id, name FROM context_definitions WHERE name = 'Esquema Data Warehouse Principal (con Políticas SQL)';


SELECT id, name, processing_config FROM context_definitions WHERE name = 'Esquema Data Warehouse Principal'

  