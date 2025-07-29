# architecture.py
from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import User
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.compute import Server
from diagrams.custom import Custom

# ==============================================================================
# URLs para Íconos Personalizados
# Esta sección es nuestra "biblioteca de íconos" a prueba de versiones
# ==============================================================================
react_url = "https://upload.wikimedia.org/wikipedia/commons/a/a7/React-icon.svg"
fastapi_url = "https://cdn.worldvectorlogo.com/logos/fastapi-1.svg"
pydantic_url = "https://raw.githubusercontent.com/pydantic/pydantic/main/docs/logo-icon.png"
openai_url = "https://openai.com/assets/images/favicon.svg"
gemini_url = "https://logowik.com/content/uploads/images/google-ai-gemini91216.logowik.com.webp"
# Nuevos íconos para evitar el error de importación
sqlalchemy_url = "https://www.sqlalchemy.org/img/sqla_logo.png"
alembic_url = "https://alembic.sqlalchemy.org/en/latest/_static/alembic.png"

# Atributos gráficos
graph_attr = {
    "fontsize": "12",
    "bgcolor": "transparent"
}

with Diagram("Arquitectura del Chatbot Avanzado 'Perseo'", show=False, graph_attr=graph_attr, direction="TB"):

    # 1. ACTORES Y CLIENTES
    admin_user = User("Admin (Equipo)")
    api_consumer_app = Server("Aplicación Cliente\n(vía API)")

    with Cluster("Frontend (Panel de Administración)"):
        admin_panel = Custom("Panel React/Vite/TS\n(con Orval)", react_url)

    # 2. SERVICIOS EXTERNOS (LLMs)
    with Cluster("Servicios de IA (Externos)"):
        llm_services = [
            Custom("OpenAI", openai_url),
            Custom("Google Gemini", gemini_url)
        ]

    # 3. BACKEND API
    with Cluster("Backend API (Python)"):
        fastapi_app = Custom("FastAPI App (main.py)", fastapi_url)

        with Cluster("a) Capa de API (app/api/endpoints)"):
            admin_endpoints = Server("Endpoints de Administración\n(CRUDs, Roles, Auth)")
            chat_endpoints = Server("Endpoint de Chat\n(/chat)")
            ingestion_endpoints = Server("Endpoint de Ingesta\n(Trigger)")
        
        with Cluster("b) Seguridad (app/security)"):
            api_key_auth = Server("API Key Auth\n(X-Application-ID)")

        with Cluster("c) Lógica de Negocio y Servicios (app/crud, app/services)"):
            crud_layer = Server("Operaciones CRUD\n(para todos los modelos)")
            ingestion_service = Server("Servicio de Ingesta\n(BackgroundTasks)")
            sql_tools = Server("Herramientas SQL\n(Utility Endpoints)")

        with Cluster("d) Capa de Datos (app/models)"):
            # AQUÍ ESTÁ EL CAMBIO PRINCIPAL
            sqlalchemy_models = Custom("Modelos ORM\n(Config, Agents, Context, etc.)", sqlalchemy_url)
            pydantic_schemas = Custom("Schemas Pydantic", pydantic_url)
            
    # 4. PERSISTENCIA Y MIGRACIONES
    with Cluster("Base de Datos"):
        db_instance = PostgreSQL("PostgreSQL DB\n'chatbot_db'")
        # Y AQUÍ EL OTRO CAMBIO
        alembic_migrations = Custom("Alembic Migrations", alembic_url)


    # 5. CONEXIONES DEL FLUJO
    admin_user >> admin_panel
    admin_panel >> Edge(label="API REST") >> admin_endpoints
    admin_endpoints >> crud_layer

    api_consumer_app >> Edge(label="X-API-Key, X-Application-ID") >> chat_endpoints
    chat_endpoints >> api_key_auth >> crud_layer
    
    admin_panel >> ingestion_endpoints
    ingestion_endpoints >> ingestion_service

    fastapi_app >> admin_endpoints
    fastapi_app >> chat_endpoints
    fastapi_app >> ingestion_endpoints
    
    crud_layer >> sqlalchemy_models
    sqlalchemy_models - Edge(color="darkgrey", style="dashed", label="valida y serializa con") - pydantic_schemas
    
    sqlalchemy_models >> Edge(label="SQLAlchemy Core") >> db_instance
    alembic_migrations >> Edge(label="gestiona esquema") >> db_instance
    crud_layer >> Edge(label="usa modelos") >> llm_services
    crud_layer >> sql_tools
    sql_tools >> Edge(label="queries directas") >> db_instance