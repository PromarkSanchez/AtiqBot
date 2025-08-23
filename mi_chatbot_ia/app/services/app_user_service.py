# app/services/app_user_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

# Asegúrate de importar tu modelo y el enum
from app.models.app_user import AppUser, AuthMethod
from app.crud import crud_app_user
from app.config import settings

class AppUserService:
    async def get_or_create_user_after_ad_auth(
        self,
        db: AsyncSession,
        ad_attributes: Dict[str, Any],
        dni_input: str 
    ) -> AppUser:
        """
        Busca un AppUser. Si no existe, lo crea explícitamente y lo prepara en la sesión.
        SIEMPRE devuelve el objeto AppUser listo para ser gestionado por el llamador.
        """
        # Determina el username a usar, tomando el del AD como prioridad
        username_ad_to_use = str(ad_attributes.get(settings.AD_USERNAME_AD_ATTRIBUTE_TO_STORE, dni_input))

        # Busca si el usuario ya existe en la base de datos local
        app_user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=username_ad_to_use)

        if app_user:
            # Si el usuario ya existe, simplemente lo devolvemos.
            print(f"APP_USER_SERVICE: Usuario AD '{username_ad_to_use}' encontrado localmente con ID {app_user.id}.")
            return app_user
        else:
            # Si el usuario no existe, lo creamos nosotros mismos aquí.
            print(f"APP_USER_SERVICE: Usuario AD '{username_ad_to_use}' no encontrado localmente. Creando explícitamente...")
            
            # 1. Creamos la instancia del modelo con los datos correctos de AD.
            new_user = AppUser(
                username_ad=username_ad_to_use,
                email=str(ad_attributes.get("mail")),
                full_name=str(ad_attributes.get("displayName")),
                auth_method=AuthMethod.AD,
                is_active_local=False  # Requisito: Crear siempre como inactivo
            )
            
            # 2. Se lo "presentamos" a la sesión de la base de datos.
            db.add(new_user)
            
            # 3. `flush()` envía el INSERT a la BD y obtiene el ID.
            await db.flush()
            
            # 4. `refresh()` actualiza nuestro objeto Python con el ID de la BD.
            await db.refresh(new_user)
            
            print(f"APP_USER_SERVICE: Usuario preparado en sesión para AD user '{username_ad_to_use}' con ID {new_user.id}")
            return new_user