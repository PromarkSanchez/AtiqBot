# app/main.py

# --- Standard Library Imports ---
# (No hay imports directos de la librería estándar en este nivel superior)

# --- Third Party Imports ---

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Application-Specific Imports ---
# Model/State Managers (si aplica a nivel global)
# from app.core.app_state import get_embedding_model_chat # Ejemplo

# Routers de Endpoints
from app.api.endpoints import (
    admin_app_users_endpoints,
    admin_auth_endpoints,
    admin_roles_endpoints,
    api_client_endpoints,
    chat_api_endpoints,
    context_definition_endpoints,
    db_connection_endpoints,
    document_source_endpoints,
    human_agent_endpoints,       # Para HumanAgent y HumanAgentGroup
    llm_model_config_endpoints,
    user_endpoints,              # Para usuarios finales del chatbot
    virtual_agent_profile_endpoints,
    admin_menus_endpoints,       # --- NUEVO ROUTER IMPORTADO ---

    # ingestion_endpoints,         # Descomentar cuando esté listo
    # admin_utility_endpoints,     # Descomentar cuando esté listo
)

# --- FastAPI Application Setup ---
# Descripción y tags para la documentación OpenAPI/Swagger
openapi_tags_metadata = [
    {"name": "Chat", "description": "Endpoints para interactuar con el chatbot y usuarios finales."},
    {"name": "Admin - Authentication", "description": "Autenticación para el panel de administración."},
    {"name": "Admin - App Users & Roles", "description": "Gestión de usuarios administradores del panel y sus roles."},
    {"name": "Admin - Menu Management", "description": "Gestión de los menús del panel de administración y sus permisos."}, # --- NUEVO TAG AÑADIDO ---
    {"name": "Admin - API Clients", "description": "Gestión de clientes API, sus claves y configuraciones."},
    {"name": "Admin - LLM Configurations", "description": "Configuración de modelos LLM, perfiles de agentes virtuales y agentes humanos."},
    {"name": "Admin - Context & Data Sources", "description": "Definición de contextos de conocimiento, fuentes de documentos y conexiones a BD."},
    {"name": "Admin - Ingestion & Utilities", "description": "Operaciones de ingesta de datos y otras utilidades de administración."},
    {"name": "Default", "description": "Endpoints por defecto o de prueba."}
]

app = FastAPI(
    title="Mi Chatbot IA Personalizable",
    description=(
        "Un backend API en Python (FastAPI) para un chatbot avanzado con IA, configurable, "
        "capaz de conectarse a diversas fuentes de contexto y con gestión de permisos para administradores."
    ),
    version="0.2.0",
    openapi_tags=openapi_tags_metadata,
    # docs_url="/api/docs",  # Ruta personalizada para Swagger UI si se desea
    # redoc_url="/api/redoc", # Ruta personalizada para ReDoc si se desea
)

# --- CORS Middleware Configuration ---
# TODO: Leer estos orígenes desde variables de entorno para producción
allowed_origins = [
    "http://localhost:5174",
    "http://localhost:5173",# Frontend de desarrollo Vite
    "http://localhost:3000",    # Posible otro frontend de desarrollo
    "http://127.0.0.1:5173",   # Acceso alternativo a Vite
    "http://190.233.213.126:5173",
    "http://190.233.213.126:5174",
    "http://100.87.87.60:5173",
    "http://127.0.0.1:5173",
    "http://100.87.87.60:5173",
 

    "null",
    # "https://your-production-frontend-domain.com", # Añadir dominio de producción
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,  # Necesario si usas autenticación basada en cookies/sesión o quieres pasar tokens así
    allow_methods=["*"],     # Permite todos los métodos estándar
    allow_headers=["*"],     # Permite todos los headers estándar y personalizados
)

# --- Application Lifecycle Events (Startup/Shutdown) ---
@app.on_event("startup")
async def app_startup_event():
    """
    Acciones a realizar cuando la aplicación FastAPI inicia.
    """
    print(f"INFO:     FastAPI Application '{app.title}' version {app.version} starting up...") # Cambiado mensaje original para más claridad
    
    # Bloque try-except para inicialización de modelos globales (si la tienes)
    try:
        # Ejemplo:
        # from app.core.app_state import initialize_global_models
        # await initialize_global_models() # O sync: initialize_global_models()
        # print("INFO:     Global models initialized successfully.")
        
        # Si no hay una función de inicialización global específica:
        print("INFO:     No specific global model initialization logic in app_startup_event.")
        
    except Exception as startup_error_obj: # <--- VARIABLE RENOMBRADA (antes era 'e')
        # Este print ahora SÍ mostrará un error real si ocurre durante tu inicialización.
        print(f"ERROR:    Failed during application startup custom logic. Error: {type(startup_error_obj).__name__} - {startup_error_obj}")
    
    print(f"INFO:     FastAPI Application '{app.title}' startup actions sequence complete.") # Cambiado mensaje original

@app.on_event("shutdown")
async def app_shutdown_event():
    """
    Acciones a realizar cuando la aplicación FastAPI se apaga.
    Ejemplo: limpiar recursos, cerrar conexiones, etc.
    """
    print(f"INFO:     FastAPI Application '{app.title}' shutting down.")


# --- API Routers Inclusion ---
# Los prefijos y tags se definen DENTRO de cada archivo de router respectivo
# para una mejor encapsulación y modularidad.

# Public / Chatbot Endpoints (asumiendo que sus prefijos NO son /admin)
app.include_router(chat_api_endpoints.router, tags=["Chat"]) # Ejemplo de tag general si el router no lo tiene
app.include_router(user_endpoints.router, tags=["Chat"])    # Ejemplo

# Administration Panel Endpoints
# Asumiendo que cada uno de estos routers ya define su prefijo (ej. /api/v1/admin/...) y su tag específico
app.include_router(admin_auth_endpoints.router)
app.include_router(admin_roles_endpoints.router)
app.include_router(admin_app_users_endpoints.router)

# --- NUEVOS ROUTERS AÑADIDOS ---
# Gestión de la estructura de menús, sus permisos por rol, y el endpoint /me/menus
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

# Routers para funcionalidades futuras (descomentar cuando estén listos)
# app.include_router(ingestion_endpoints.router)
# app.include_router(admin_utility_endpoints.router)


# --- Root and Test Endpoints ---
@app.get("/", tags=["Default"], summary="Root Endpoint")
async def read_root():
    """
    Endpoint raíz que devuelve un mensaje de bienvenida.
    Útil para una verificación rápida de que el servidor está funcionando.
    """
    return {"message": f"¡Bienvenido al Backend de {app.title} v{app.version}!"}

@app.get("/health", tags=["Default"], summary="Health Check Endpoint")
async def health_check():
    """
    Endpoint de verificación de salud simple.
    """
    return {"status": "ok", "message": "API is healthy."}

# Elimino /test si /health ya cumple esa función de "ping".
# Si /test es para algo más específico, puedes mantenerlo.
# @app.get("/test", tags=["Default"])
# async def test_endpoint():
#     return {"status": "ok", "message": "El endpoint de prueba funciona!"}