# app/services/app_user_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List

from app.models.app_user import AppUser
from app.crud import crud_app_user, crud_role # Asume que crud_app_user y crud_role existen
from app.config import settings

class AppUserService:
    async def get_or_create_user_after_ad_auth(
        self,
        db: AsyncSession,
        ad_attributes: Dict[str, Any],
        # El DNI que el usuario ingresó, para usarlo como username_ad si no viene de AD explícitamente
        dni_input: str 
    ) -> Optional[AppUser]:
        """
        Busca un AppUser por su identificador de AD. Si no existe, lo crea.
        Actualiza email y full_name si vienen de AD.
        Devuelve el objeto AppUser o None si hay un problema.
        """
        # El atributo que usamos como identificador único de AD en nuestra tabla AppUser
        # Por tu prueba, sAMAccountName parece ser el DNI y es una buena opción.
        username_ad_from_ad = ad_attributes.get(settings.AD_USERNAME_AD_ATTRIBUTE_TO_STORE) # Ej. "sAMAccountName"

        if not username_ad_from_ad:
            # Si el atributo clave no vino de AD, podríamos usar el dni_input como fallback si es el mismo.
            # O podríamos lanzar un error si es obligatorio que AD devuelva este atributo.
            # Dado que tu AD SÍ devuelve sAMAccountName = DNI, esto debería funcionar.
            # Si AD_USERNAME_AD_ATTRIBUTE_TO_STORE fuera 'userPrincipalName' y quisiéramos guardar DNI,
            # necesitaríamos ajustar aquí. Por ahora, si es sAMAccountName y es DNI:
            if settings.AD_USERNAME_AD_ATTRIBUTE_TO_STORE.lower() == "samaccountname":
                username_ad_to_use = dni_input
            else:
                print(f"ERROR APP_USER_SERVICE: El atributo clave de AD '{settings.AD_USERNAME_AD_ATTRIBUTE_TO_STORE}' "
                     f"no fue encontrado en los atributos de AD para DNI {dni_input}. Atributos: {ad_attributes}")
                return None
        else:
            username_ad_to_use = str(username_ad_from_ad)

        app_user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=username_ad_to_use)

        email_from_ad = ad_attributes.get("mail")
        full_name_from_ad = ad_attributes.get("displayName") # O 'cn' si prefieres

        if not app_user:
            print(f"APP_USER_SERVICE: Usuario AD '{username_ad_to_use}' no encontrado localmente. Creando...")
            # TODO: Decidir roles iniciales. Por ahora, sin roles o un rol "default_admin_user" si lo creas.
            app_user = await crud_app_user.create_app_user_internal(
                db,
                username_ad=username_ad_to_use,
                email=str(email_from_ad) if email_from_ad else None,
                full_name=str(full_name_from_ad) if full_name_from_ad else None,
                is_active_local=True, # Por defecto, activo si AD autenticó
                # initial_roles_names=["admin_viewer"] # Ejemplo si tuvieras un rol por defecto
            )
            print(f"APP_USER_SERVICE: Usuario local creado para AD user '{username_ad_to_use}' con ID {app_user.id}")
        else:
            print(f"APP_USER_SERVICE: Usuario AD '{username_ad_to_use}' encontrado localmente con ID {app_user.id}.")
            # Opcional: Actualizar email/nombre desde AD si han cambiado
            updated = False
            if email_from_ad and app_user.email != email_from_ad:
                app_user.email = str(email_from_ad)
                updated = True
            if full_name_from_ad and app_user.full_name != full_name_from_ad:
                app_user.full_name = str(full_name_from_ad)
                updated = True
            
            if updated:
                db.add(app_user)
                await db.commit()
                await db.refresh(app_user)
                print(f"APP_USER_SERVICE: Datos locales actualizados para usuario ID {app_user.id} desde AD.")
        
        if not app_user.is_active_local:
            print(f"APP_USER_SERVICE: Usuario '{username_ad_to_use}' (ID: {app_user.id}) está INACTIVO localmente. Acceso denegado.")
            return None # Aunque AD autentique, si está inactivo localmente, no procede.
            
        return app_user