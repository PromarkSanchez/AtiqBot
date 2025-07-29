SELECT uuid, name, cmetadata AS collection_metadata
FROM langchain_pg_collection
WHERE name = 'chatbot_knowledge_base_v1';

SELECT *  
FROM langchain_pg_embedding
WHERE collection_id = 'd5d6eb1d-054b-4bbe-b8f9-cb2bb0545941'; 

SELECT 
    document AS chunk_text,
    cmetadata ->> 'context_name' AS context_name,
    cmetadata ->> 'context_id' AS context_id,
    cmetadata ->> 'source_filename' AS source_filename,
    cmetadata ->> 'source_page_number' AS source_page_number, -- Será NULL para TXT
    cmetadata -- Para ver todos los metadatos del chunk
FROM langchain_pg_embedding
WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'chatbot_knowledge_base_v1')
  AND cmetadata ->> 'context_name' = 'Contexto General Estudiantil' -- Filtra por tu contexto documental
LIMIT 5; -- Muestra los primeros 5 para no inundar


-- En chatbot_db
DROP TABLE IF EXISTS interaction_logs;

SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'langchain_pg_embedding';

