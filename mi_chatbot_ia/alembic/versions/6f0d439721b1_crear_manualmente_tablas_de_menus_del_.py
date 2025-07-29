"""Crear manualmente tablas de menus del panel

Revision ID: a1b2c3d4e5f6  # <--- Asegúrate que este ID coincide con el nombre de tu archivo
Revises: d54b71c4a036
Create Date: 2025-06-12 13:00:00.000000 # <-- La fecha será diferente

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Asegúrate de que 'revision' y 'down_revision' sean los correctos para tu nuevo archivo.
# Alembic los genera por ti. Si son diferentes, déjalos como están.
revision: str = 'a1b2c3d4e5f6' # <-- AJUSTA ESTO AL ID DE TU NUEVO ARCHIVO
down_revision: Union[str, None] = 'd54b71c4a036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea las tablas para los menús y sus permisos."""
    print("Ejecutando migración manual: Creando 'admin_panel_menus' y 'admin_role_menu_permissions'")
    
    op.create_table('admin_panel_menus',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, comment="Nombre del menú para la UI"),
        sa.Column('frontend_route', sa.String(length=255), nullable=False, comment="Ruta en el frontend"),
        sa.Column('icon_name', sa.String(length=100), nullable=True, comment="Nombre del icono para el frontend"),
        sa.Column('parent_id', sa.Integer(), nullable=True, comment="Para anidar menús"),
        sa.Column('display_order', sa.Integer(), server_default='100', nullable=False, comment="Orden para mostrar en la UI"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['admin_panel_menus.id'], name=op.f('fk_admin_panel_menus_parent_id')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_panel_menus')),
        sa.UniqueConstraint('frontend_route', name=op.f('uq_admin_panel_menus_frontend_route')),
        sa.UniqueConstraint('name', name=op.f('uq_admin_panel_menus_name'))
    )
    
    op.create_table('admin_role_menu_permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('menu_id', sa.Integer(), nullable=False),
        sa.Column('can_view', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['menu_id'], ['admin_panel_menus.id'], name=op.f('fk_admin_role_menu_permissions_menu_id'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_admin_role_menu_permissions_role_id'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_role_menu_permissions'))
    )
    print("Migración manual completada con éxito.")


def downgrade() -> None:
    """Elimina las tablas de menús y permisos."""
    print("Ejecutando downgrade: Eliminando 'admin_role_menu_permissions' y 'admin_panel_menus'")
    op.drop_table('admin_role_menu_permissions')
    op.drop_table('admin_panel_menus')
    print("Downgrade completado.")