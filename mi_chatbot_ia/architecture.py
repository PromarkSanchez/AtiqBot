# architecture_v13_final.py
from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.custom import Custom
from diagrams.onprem.client import User

graph_attr = { "splines": "ortho", "fontsize": "12", "rankdir": "LR", "nodesep": "1.0", "ranksep": "2.2" }

with Diagram("Arquitectura Detallada de ChatBot Multi-Cliente (con Routing)", show=False, graph_attr=graph_attr):

    # 1. Interfaces y Actores
    with Cluster("Usuarios y Clientes"):
        admin_user = User("Admin del Sistema")
        human_agent_user = Custom("Agente Humano", "./icons/human.png")
        with Cluster("Consumidores de la API"):
            api_consumers = [
                Custom("Cliente Web", "./icons/web_client.png"),
                Custom("Cliente API Genérico", "./icons/api_client.png")
            ]
        with Cluster("Panel de Administración"):
             admin_panel = Custom("Frontend\n(React/Vite/TS)", "./icons/react.png")

    # 2. Backend API
    with Cluster("Backend API (FastAPI)"):
        fastapi_app = Custom("FastAPI App\n/api/v1/chat", "./icons/fastapi.png")
        auth_layer = Custom("Seguridad\n(X-API-Key)", "./icons/auth.png")
        
        # EL CORAZÓN DE LA LÓGICA CON EL ROUTING
        with Cluster("Core Chat Logic"):
            router = Custom("Router Lógico\n(is_sql_intent)", "./icons/router.png")
            
            with Cluster("Cadena RAG Documental"):
                rag_chain = [
                    Custom("Recuperar Vectores\n(metadata filter)", "./icons/db_source.png"),
                    Custom("Generar Respuesta\ncon Contexto", "./icons/logic.png")
                ]
            
            with Cluster("Cadena Text-to-SQL"):
                sql_chain = [
                    Custom("Generar DDL\npara Contexto", "./icons/sqlalchemy.png"),
                    Custom("LLM genera SQL", "./icons/logic.png"),
                    Custom("Ejecutar y Generar\nRespuesta Natural", "./icons/db_source.png")
                ]
        
        redis_cache = Redis("Redis\nCache")

    # 3. Almacenamiento y Servicios Externos
    with Cluster("Bases de Datos Persistentes"):
        with Cluster("Servidor PostgreSQL Principal"):
            # Dividimos la DB en sus componentes lógicos
            config_db = PostgreSQL("Config, Logs y\nChat History")
            vector_db = Custom("Vector Store\n(pgvector)", "./icons/pgvector.png") # Icono específico para pgvector, o puedes usar docs.png
        
        data_warehouse = PostgreSQL("Data Warehouse\n(DW)")

    with Cluster("Servicios Externos de IA (LLMs)"):
        llm_services = [Custom("Google Gemini", "./icons/gemini.png"), Custom("OpenAI GPT", "./icons/openai.png")]
    
    with Cluster("Ingesta de Datos (Offline)"):
         ingestion_service = Custom("Servicio de Ingesta", "./icons/python.png")
         ingestion_service >> vector_db
    
    # CONEXIONES Y FLUJOS
    
    admin_user >> admin_panel >> fastapi_app
    
    # FLUJO PRINCIPAL DE CHAT
    api_consumers >> Edge(label="1. Petición a /chat") >> fastapi_app
    fastapi_app >> auth_layer >> router # La petición autorizada va al router

    # Rutas desde el router
    router >> Edge(label="Intención: Pregunta Documental") >> rag_chain[0]
    router >> Edge(label="Intención: Consulta de Datos") >> sql_chain[0]

    # Conexiones de la cadena RAG
    rag_chain[0] >> vector_db
    rag_chain[0] >> rag_chain[1] >> llm_services
    
    # Conexiones de la cadena Text-to-SQL
    sql_chain[0] >> data_warehouse # Se conecta al DW para inspeccionar el schema
    sql_chain[0] >> sql_chain[1] >> llm_services
    sql_chain[1] >> sql_chain[2] >> data_warehouse # Se conecta al DW para ejecutar el SQL

    # Salida de las cadenas y handoff
    rag_chain[1] >> Edge(label="Respuesta Final\n+ Fuentes") >> redis_cache
    sql_chain[2] >> Edge(label="Respuesta Final\n+ Fuentes") >> redis_cache
    
    # Conexiones de historial y handoff
    router >> Edge(style="dashed") >> config_db # Para leer/escribir historial de chat
    router >> Edge(label="Trigger de Handoff", style="bold", color="#dc3545") >> human_agent_user
    human_agent_user >> router # El humano responde a través del sistema

    # Respuesta al cliente y feedback
    redis_cache >> api_consumers
    api_consumers >> Edge(label="Feedback", style="dashed", color="#007bff") >> fastapi_app >> config_db