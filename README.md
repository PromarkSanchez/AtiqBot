# AtiqBot: Plataforma de Creación y Gestión de Asistentes de IA

**AtiqBot** es un proyecto personal que evoluciona el concepto de chatbot a una plataforma integral de IA conversacional. Permite a los administradores, sin necesidad de código, construir, configurar y desplegar agentes de IA multi-modelo que se conectan de forma segura a diversas fuentes de conocimiento, como bases de datos internas y sistemas de gestión documental.

![Captura de pantalla del Panel de Administración](https://atiqtec.com/img/atiqBot.jpg)

---

## ✨ Características Principales

*   **Centro de Control Visual (AIOps):** Un completo panel de administración construido en React/TypeScript para gestionar cada aspecto de la plataforma:
    *   **Gestión de Agentes Virtuales:** Crea múltiples "personalidades" de IA con prompts, modelos y configuraciones únicas.
    *   **Gestión de Conocimiento Centralizada:** Define "Contextos" que conectan a los agentes con bases de datos SQL o colecciones de documentos.
    *   **Inspección de Bases de Datos en Vivo:** Conéctate a bases de datos (PostgreSQL, SQL Server) e inspecciona sus tablas directamente desde la interfaz.
    *   **Ingesta de Documentos:** Sube y procesa archivos (PDF, DOCX, XLSX) para que sirvan de conocimiento a los agentes de IA (RAG).

*   **Arquitectura Multi-Modelo y Multi-Proveedor:**
    *   **Cero Dependencia:** Soporte integrado para múltiples proveedores de LLM (Google Gemini, OpenAI, AWS Bedrock) y modelos locales (Ollama).
    *   **Enrutador de Intenciones Inteligente:** Un agente maestro analiza la pregunta del usuario para dirigirla al especialista adecuado (consultas a BD vs. búsqueda en documentos).

*   **IA que Crea IA:**
    *   **Asistente de Creación de Prompts:** Una innovadora herramienta que, a partir de una descripción en lenguaje natural del objetivo del agente, utiliza un LLM maestro para generar los `system prompts` optimizados.

*   **Seguridad de Nivel Empresarial:**
    *   **Autenticación Robusta:** Integración completa con Active Directory (AD), JWT y Autenticación Multifactor (MFA).
    *   **Roles y Permisos Granulares:** Sistema de control de acceso que permite definir qué administradores pueden ver y modificar cada sección del panel.

*   **Despliegue Sencillo:**
    *   **Gestor de Clientes API:** Crea y gestiona claves de API para diferentes aplicaciones o departamentos, cada una con acceso a contextos específicos.
    *   **Widget Personalizable:** Un personalizador visual para el widget de chat, permitiendo adaptar colores, textos y avatares a cualquier marca, con un código de inserción listo para usar.

---

## 🛠️ Pila Tecnológica

*   **Backend:** Python 3.11+, FastAPI, SQLAlchemy, LangChain, Celery (potencial), Redis.
*   **Frontend:** React 18+, TypeScript, Vite, Tailwind CSS, TanStack Query.
*   **Bases de Datos:** PostgreSQL con la extensión `pgvector` para búsquedas de similitud.
*   **Autenticación:** JWT, Integración con Active Directory (LDAP), MFA (TOTP).
*   **Despliegue:** Docker (potencial), Gunicorn.

---

## 🚀 Cómo Empezar

*Instrucciones de alto nivel sobre cómo un desarrollador podría poner en marcha el proyecto.*

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/PromarkSanchez/AtiqBot
    cd AtiqBot
    ```

2.  **Configurar el Backend:**
    *   Crear y activar un entorno virtual.
    *   Instalar dependencias: `pip install -r requirements.txt`.
    *   Crear un archivo `.env` basado en `.env.example` y llenar las variables (claves de API, URLs de BD, etc.).
    *   Ejecutar las migraciones de la base de datos con Alembic.
    *   Iniciar el servidor: `uvicorn app.main:app --reload`.

3.  **Configurar el Frontend:**
    *   Navegar a la carpeta `FRONTEND/chatbot-admin-panel`.
    *   Instalar dependencias: `npm install`.
    *   Crear un archivo `.env` y configurar `VITE_API_BASE_URL` para que apunte a tu backend.
    *   Iniciar el servidor de desarrollo: `npm run dev`.

---

## 📜 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## 💬 Contacto

Perseo Sánchez - [Linkedin](https://www.linkedin.com/in/perseo-sanchez-valverde-7075b4110/) - https://atiqtec.com
