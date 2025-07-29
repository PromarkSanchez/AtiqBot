# app/security/role_auth.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.models.app_user import AppUser
# La importación de get_current_active_admin_user depende de dónde la tengas, ajusta si es necesario
from app.api.endpoints.admin_auth_endpoints import get_current_active_admin_user
from app.db.session import get_crud_db_session

# NUEVA IMPORTACIÓN para acceder a la lógica de menús
from app.crud import crud_admin_menu

class AuthChecker:
    def __init__(self, 
                 required_roles: Optional[List[str]] = None, 
                 required_menu_name: Optional[str] = None):
        
        if not required_roles and not required_menu_name:
            raise ValueError("AuthChecker requiere al menos 'required_roles' o 'required_menu_name'.")
            
        self.required_roles = set(required_roles) if required_roles else set()
        self.required_menu_name = required_menu_name

    async def __call__(
        self, 
        current_user: AppUser = Depends(get_current_active_admin_user),
        db: AsyncSession = Depends(get_crud_db_session) # <--- Ahora necesita la sesión de BD
    ) -> AppUser:
        
        # 1. Comprobación de rol (la que ya tenías, como un chequeo básico)
        if self.required_roles:
            user_role_names = {role.name for role in current_user.roles}
            if not self.required_roles.intersection(user_role_names):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado. No posee el rol requerido. Se necesita uno de: {', '.join(self.required_roles)}.",
                )

        # 2. NUEVA Comprobación de permiso de menú (si se especificó)
        if self.required_menu_name:
            # Si es SuperAdmin, siempre tiene acceso
            if any(role.name == "SuperAdmin" for role in current_user.roles):
                return current_user # Bypass para SuperAdmin

            # Consultamos los menús autorizados para el usuario
            authorized_menus = await crud_admin_menu.get_authorized_menus_for_user(db, user=current_user)
            
            # Verificamos si alguno de los menús autorizados tiene el nombre requerido
            if not any(menu.name == self.required_menu_name for menu in authorized_menus):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado. No tiene permiso para acceder al recurso '{self.required_menu_name}'.",
                )
        
        # Si pasó todas las comprobaciones, devolvemos el usuario
        return current_user

# Función helper, ahora renombrada para mayor claridad
def require_roles(
    roles: Optional[List[str]] = None, 
    menu_name: Optional[str] = None
) -> AuthChecker:
    return AuthChecker(required_roles=roles, required_menu_name=menu_name)