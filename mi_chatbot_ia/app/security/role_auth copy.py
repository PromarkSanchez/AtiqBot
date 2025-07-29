# app/security/role_auth.py
from fastapi import Depends, HTTPException, status  # type: ignore
from typing import List, Set

from app.models.app_user import AppUser # Modelo para el tipado de current_user
# Importar la dependencia que obtiene el usuario completamente autenticado
# ¡Asegúrate de que la ruta de importación sea correcta!
# Si auth_api.py está en app/api/v1/admin/auth_api.py
from app.api.endpoints.admin_auth_endpoints import get_current_active_admin_user 

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        if not allowed_roles:
            # Es un error de programación usar RoleChecker sin especificar qué roles están permitidos.
            # Si una ruta solo necesita autenticación pero no roles, se usa get_current_active_admin_user directamente.
            raise ValueError("La lista de 'allowed_roles' no puede estar vacía al inicializar RoleChecker.")
        self.allowed_roles = set(allowed_roles) 

    async def __call__(self, current_user: AppUser = Depends(get_current_active_admin_user)) -> AppUser:
        """
        Verifica si el usuario 'current_user' (obtenido de get_current_active_admin_user)
        tiene al menos uno de los roles en self.allowed_roles.
        Devuelve el objeto AppUser si está autorizado, de lo contrario lanza HTTPException 403.
        """
        # Cargar los nombres de los roles del usuario de forma segura
        user_role_names: Set[str] = set()
        if current_user.roles: # Verificar que la lista de roles no sea None o vacía
            for role in current_user.roles:
                if role and hasattr(role, 'name') and role.name: # Asegurar que el rol y su nombre no sean None/vacío
                    user_role_names.add(role.name)
        
        print(f"ROLE_CHECKER: Usuario: '{current_user.username_ad}', Roles del Usuario: {user_role_names}, Roles Requeridos: {self.allowed_roles}")

        # Verificar si hay alguna intersección entre los roles del usuario y los roles permitidos
        if not self.allowed_roles.intersection(user_role_names):
            print(f"ROLE_CHECKER: DENEGADO - Usuario: '{current_user.username_ad}'. "
                  f"Roles: {user_role_names}, Requeridos: {self.allowed_roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. No posee los permisos de rol necesarios. Se requiere uno de: {', '.join(self.allowed_roles)}.",
            )
        
        print(f"ROLE_CHECKER: CONCEDIDO - Usuario: '{current_user.username_ad}' tiene un rol permitido.")
        return current_user # Devolver el usuario para que el endpoint lo pueda usar

# Función helper para hacer la dependencia más legible en los endpoints de FastAPI
def require_roles(roles_needed: List[str]) -> RoleChecker:
    """
    Crea una instancia de RoleChecker para ser usada como una dependencia de FastAPI.
    Ejemplo de uso en un endpoint: current_user: AppUser = Depends(require_roles(["Admin", "Editor"]))
    """
    if not isinstance(roles_needed, list) or not roles_needed: # roles_needed no debe ser una lista vacía
        raise TypeError("require_roles espera una lista no vacía de strings de nombres de rol.")
    return RoleChecker(allowed_roles=roles_needed)