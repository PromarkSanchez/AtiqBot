# create_local_user.py
import enum
# La línea clave es la siguiente:
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLAlchemyEnum 
from sqlalchemy.orm import relationship 
from sqlalchemy.sql import func 
from app.db.session import Base_CRUD 
from app.models.role import Role
from .user_role_association import user_role_association

# --- CONFIGURACIÓN ---
# ¡Ajusta estas variables!
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot_db"

NUEVO_USERNAME = "46990588"
NUEVA_PASSWORD = "claveSegura123"
NUEVO_EMAIL = "local@test.com"
NUEVO_NOMBRE_COMPLETO = "Usuario De Prueba Local"
# ---------------------

# Importaciones de tu proyecto (ajusta las rutas si es necesario)
from app.utils.security_utils import get_password_hash
from app.models.app_user import AppUser, AuthMethod

# Función principal asíncrona
async def main():
    print("Conectando a la base de datos...")
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionFactory() as session:
        print(f"Creando usuario de prueba: '{NUEVO_USERNAME}'")
        
        # Hasheamos la contraseña
        hashed_password = get_password_hash(NUEVA_PASSWORD)
        print(f"Password hasheada: {hashed_password[:30]}...")

        # Creamos la instancia del nuevo usuario
        nuevo_usuario = AppUser(
            username_ad=NUEVO_USERNAME,  # Usamos el mismo campo
            email=NUEVO_EMAIL,
            full_name=NUEVO_NOMBRE_COMPLETO,
            is_active_local=True,
            
            # --- La magia está aquí ---
            auth_method=AuthMethod.LOCAL,
            hashed_password=hashed_password,
            # --------------------------

            mfa_enabled=False # Empezamos sin MFA para este usuario
        )

        session.add(nuevo_usuario)
        await session.commit()

    await engine.dispose()
    print("¡Usuario local creado exitosamente!")
    print("\n--- DETALLES ---")
    print(f"Username: {NUEVO_USERNAME}")
    print(f"Password: {NUEVA_PASSWORD}")
    print("----------------")
    print("\nAhora puedes intentar iniciar sesión con estas credenciales.")


# Ejecutar el script
if __name__ == "__main__":
    # Necesitas importar tu configuración de settings para que Fernet funcione si tu security_utils lo necesita al cargar.
    try:
        from app.config import settings
        # Si get_password_hash no depende de Fernet, esta línea es opcional pero segura de incluir.
    except ImportError:
        print("Advertencia: No se pudo importar la configuración. Esto podría fallar si get_password_hash la necesita.")

    asyncio.run(main())