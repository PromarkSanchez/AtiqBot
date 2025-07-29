# app/main.py

# --- Third Party Imports ---
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.app_state import initialize_global_models

from app.api.endpoints import (
    admin_app_users_endpoints,
    admin_auth_endpoints,
    admin_roles_endpoints,
    api_client_endpoints,
    chat_api_endpoints,
    context_definition_endpoints,
    db_connection_endpoints,
    document_source_endpoints,
    human_agent_endpoints,
    llm_model_config_endpoints,
    user_endpoints,
    virtual_agent_profile_endpoints,
    admin_menus_endpoints,
)

# --- FastAPI Application Setup ---
# Descripción y tags para la documentación OpenAPI/Swagger
openapi_tags_metadata = [
    {"name": "Chat", "description": "Endpoints para interactuar con el chatbot y usuarios finales."},
    {"name": "Admin - Authentication", "description": "Autenticación para el panel de administración."},
    {"name": "Admin - App Users & Roles", "description": "Gestión de usuarios administradores del panel y sus roles."},
    {"name": "Admin - Menu Management", "description": "Gestión de los menús del panel de administración y sus permisos."},
    {"name": "Admin - API Clients", "description": "Gestión de clientes API, sus claves y configuraciones."},
    {"name": "Admin - LLM Configurations", "description": "Configuración de modelos LLM, perfiles de agentes virtuales y agentes humanos."},
    {"name": "Admin - Context & Data Sources", "description": "Definición de contextos de conocimiento, fuentes de documentos y conexiones a BD."},
    {"name": "Admin - Ingestion & Utilities", "description": "Operaciones de ingesta de datos y otras utilidades de administración."},
    {"name": "Default", "description": "Endpoints por defecto o de prueba."}
]


# ==========================================================
# ======>     LIFESPAN MANAGER (STARTUP/SHUTDOWN)    <======
# ==========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código que se ejecuta ANTES de que la aplicación empiece a recibir peticiones
    print(f"INFO:     FastAPI Application '{app.title}' version {app.version} starting up...")
    print("INFO:     Executing startup logic: Initializing global models...")
    
    try:
        # Llamamos a la función para cargar los modelos pesados
        initialize_global_models()
        print("INFO:     Global models initialized successfully.")
    except Exception as e:
        print(f"ERROR:    CRITICAL FAILURE DURING STARTUP. Models could not be loaded: {e}")
    
    print(f"INFO:     FastAPI Application startup actions sequence complete.")
    
    yield # La aplicación se ejecuta en este punto
    
    # Código que se ejecuta cuando la aplicación se apaga
    print(f"INFO:     FastAPI Application '{app.title}' shutting down.")

# --- Instancia de la Aplicación FastAPI ---
app = FastAPI(
    title="Mi Chatbot IA Personalizable",
    description=(
        "Un backend API en Python (FastAPI) para un chatbot avanzado con IA, configurable, "
        "capaz de conectarse a diversas fuentes de contexto y con gestión de permisos para administradores."
    ),
    version="0.2.0",
    openapi_tags=openapi_tags_metadata,
    lifespan=lifespan  # Se registra el manejador de ciclo de vida
)

# --- CORS Middleware Configuration ---
allowed_origins = [
    # Orígenes de Desarrollo Local
    "http://localhost:8000",
    "http://localhost:5173",
    "http://localhost:5173",
    # Orígenes de Producción (tu IP pública y privada de EC2)
    "http://3.227.128.241:5173", # <-- LA MÁS IMPORTANTE
    "http://172.31.35.254:5173",
    # Otros casos especiales que tenías
    "https://upch-test.blackboard.com",
    "https://admin-ia.cayetano.pe",
    "https://admin-ia-back.cayetano.pe",
    "admin-ia-back.cayetano.pe"
    "https://cayetano.pe",
    "null",
    "http://172.17.100.75"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- API Routers Inclusion ---
# Public / Chatbot Endpoints
app.include_router(chat_api_endpoints.router)
app.include_router(user_endpoints.router)

# Administration Panel Endpoints
app.include_router(admin_auth_endpoints.router)
app.include_router(admin_roles_endpoints.router)
app.include_router(admin_app_users_endpoints.router)
app.include_router(admin_menus_endpoints.router)
app.include_router(admin_menus_endpoints.router_perms)
app.include_router(admin_menus_endpoints.router_me)
app.include_router(api_client_endpoints.router)
app.include_router(context_definition_endpoints.router)
app.include_router(document_source_endpoints.router)
app.include_router(db_connection_endpoints.router)
app.include_router(llm_model_config_endpoints.router)
app.include_router(virtual_agent_profile_endpoints.router)
app.include_router(human_agent_endpoints.router)

# --- Root and Test Endpoints ---
@app.get("/", tags=["Default"], summary="Root Endpoint", include_in_schema=False)
async def read_root():
    return {"message": f"¡Bienvenido al Backend de {app.title} v{app.version}!"}

@app.get("/health", tags=["Default"], summary="Health Check Endpoint")
async def health_check():
    return {"status": "ok", "message": "API is healthy."}