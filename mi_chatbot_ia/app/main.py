# app/main.py

# --- Python Standard Library Imports ---
import traceback
from contextlib import asynccontextmanager

# --- Third Party Imports ---
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Local Application Imports ---
# NOTA: Importa la función de inicialización directamente. No todo el estado global.
from app.core.app_state import initialize_application 
# Importación agrupada de routers para mayor claridad
from app.api.endpoints import admin_app_users_endpoints
from app.api.endpoints import admin_auth_endpoints
from app.api.endpoints import admin_menus_endpoints
from app.api.endpoints import admin_roles_endpoints
from app.api.endpoints import api_client_endpoints
from app.api.endpoints import chat_api_endpoints
from app.api.endpoints import context_definition_endpoints
from app.api.endpoints import db_connection_endpoints
from app.api.endpoints import document_source_endpoints
from app.api.endpoints import human_agent_endpoints
from app.api.endpoints import llm_model_config_endpoints
from app.api.endpoints import user_endpoints
from app.api.endpoints import virtual_agent_profile_endpoints
from app.api.endpoints import admin_ingestion_endpoints # <-- AÑADIR ESTA LÍNEA

from app.config import settings # Asumo que tienes un config.py con un objeto `settings`

# ==========================================================
# ======>   LIFESPAN MANAGEMENT (INICIO Y CIERRE)      <======
# ==========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\nINFO:     [STARTUP] FastAPI App '{app.title}' v{app.version} iniciando...")
    try:
        # LLAMADA ASÍNCRONA: Inicializa y guarda el estado en la app
        app.state.app_state = await initialize_application()

        print("INFO:     [STARTUP] ¡Todos los recursos y conexiones se han inicializado con éxito!")
        yield
    except Exception:
        # ... el resto del try/except es igual ...
        print("--- !!! ARRANQUE FALLIDO - ERROR CRÍTICO IRRECUPERABLE !!! ---")
        traceback.print_exc()
        print("--- LA APLICACIÓN NO PUEDE ARRANCAR. APAGANDO. ---")
    finally:
        # LLAMADA AL CIERRE: Esto cierra las conexiones de la base de datos
        print("\nINFO:     [SHUTDOWN] Servidor apagándose. Limpiando recursos...")
        if hasattr(app.state, 'app_state') and app.state.app_state:
            await app.state.app_state.close()
        print("INFO:     [SHUTDOWN] Recursos cerrados correctamente.")

# ==========================================================
# ======>      DEFINICIÓN DE LA APLICACIÓN FASTAPI     <======
# ==========================================================

# --- Documentación OpenAPI (Swagger/ReDoc) ---
# MEJORA: Define esto como una variable para mantener el constructor de FastAPI limpio.
openapi_tags_metadata = [
    # (Tus tags estaban perfectos, los mantengo)
    {"name": "Chat", "description": "Endpoints para interactuar con el chatbot y usuarios finales."},
    {"name": "Admin - Authentication", "description": "Autenticación para el panel de administración."},
    {"name": "Admin - App Users & Roles", "description": "Gestión de usuarios administradores del panel y sus roles."},
    {"name": "Admin - Menu Management", "description": "Gestión de los menús del panel de administración y sus permisos."},
    {"name": "Admin - API Clients", "description": "Gestión de clientes API, sus claves y configuraciones."},
    {"name": "Admin - LLM Configurations", "description": "Configuración de modelos LLM, perfiles de agentes virtuales y agentes humanos."},
    {"name": "Admin - Context & Data Sources", "description": "Definición de contextos de conocimiento, fuentes de documentos y conexiones a BD."},
    {"name": "Admin - Ingestion & Utilities", "description": "Operaciones de ingesta de datos y otras utilidades de administración."},
    {"name": "Default", "description": "Endpoints por defecto o de prueba."},
    
]

# --- Desactivar la documentación en producción ---
# TU RESPUESTA: Para apagar los docs, pasa estos parámetros.
# En un escenario real, harías esto condicional basado en una variable de entorno.
# Ejemplo: docs_url=None if settings.ENVIRONMENT == "production" else "/docs"
fastapi_app_kwargs = {
    "title": "AdminBot power by Atiqtec.com",
    "description": (
        "Backend creado por AtiqTec.com, cualquier duda o consulta 972588411"
        "Este Backend es capaz de conectarse a diversas fuentes de contexto y con gestión de permisos para administradores."
    ),
    "version": "0.2.0",
    "openapi_tags": openapi_tags_metadata,
    "lifespan": lifespan
}

# La condición para activar/desactivar los docs.
# Lee una variable de entorno. Si no está, asume que no es producción.
if settings.ENVIRONMENT == "production":
    print("INFO:     Modo de producción detectado. Desactivando documentación API (Swagger/ReDoc).")
    fastapi_app_kwargs["docs_url"] = None
    fastapi_app_kwargs["redoc_url"] = None

# --- Creación de la Instancia de la App ---
app = FastAPI(**fastapi_app_kwargs)

# ==========================================================
# ======>            MIDDLEWARE (CORS)                 <======
# ==========================================================
# MEJORA: Es más seguro leer estos orígenes desde una variable de entorno.
# Ejemplo: settings.ALLOWED_ORIGINS.split(',')
# La lista que tenías es para desarrollo. ¡Ten cuidado con "null" y wildcards en producción!
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # Leer de config.py
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# ======>             INCLUSIÓN DE ROUTERS             <======
# ==========================================================
# MEJORA: Agrupar routers por funcionalidad para facilitar la lectura.

# ESTA ES LA VERSIÓN CORREGIDA QUE RESTAURARÁ TUS URLs

# --- Public & Chat Endpoints ---
# Asumimos que estos ya no tenían prefijo, pero si lo tenían, quítaselo también
app.include_router(chat_api_endpoints.router, tags=["Chat"])
app.include_router(user_endpoints.router, tags=["Chat"])

# --- Administration Panel Endpoints ---
# ¡SIN PREFIJOS! FastAPI usará los prefijos definidos DENTRO de cada archivo de endpoint.
app.include_router(admin_auth_endpoints.router, tags=["Admin - Authentication"])
app.include_router(admin_roles_endpoints.router, tags=["Admin - App Users & Roles"])
app.include_router(admin_app_users_endpoints.router, tags=["Admin - App Users & Roles"])
app.include_router(admin_menus_endpoints.router, tags=["Admin - Menu Management"])
app.include_router(admin_menus_endpoints.router_perms, tags=["Admin - Menu Management"])
app.include_router(admin_menus_endpoints.router_me, tags=["Admin - Menu Management"])

# --- API & Data Configuration Endpoints ---
app.include_router(api_client_endpoints.router, tags=["Admin - API Clients"])
app.include_router(api_client_endpoints.public_router, tags=["Public - Webchat"])

app.include_router(context_definition_endpoints.router, tags=["Admin - Context & Data Sources"])
app.include_router(document_source_endpoints.router, tags=["Admin - Context & Data Sources"])
app.include_router(db_connection_endpoints.router, tags=["Admin - Context & Data Sources"])
app.include_router(llm_model_config_endpoints.router, tags=["Admin - LLM Configurations"])
app.include_router(virtual_agent_profile_endpoints.router, tags=["Admin - LLM Configurations"])
app.include_router(human_agent_endpoints.router, tags=["Admin - LLM Configurations"])
app.include_router(admin_ingestion_endpoints.router, tags=["Admin - Ingestion & Utilities"]) # <-- AÑADIR ESTA LÍNEA

# --- Root and Health Check ---
@app.get("/", tags=["Default"], include_in_schema=False)
def read_root():
    return {"message": f"¡Bienvenido al Backend de {app.title} v{app.version}!"}

@app.get("/health", tags=["Default"])
def health_check():
    """Endpoint de monitoreo para verificar que la aplicación está viva."""
    return {"status": "ok"}