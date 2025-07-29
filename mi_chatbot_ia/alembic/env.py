# alembic/env.py
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- INICIO SECCIÓN MODIFICADA POR NOSOTROS ---
# 1. Añadir la raíz del proyecto (un nivel arriba de 'alembic/') al sys.path
# Esto permite que Python encuentre el paquete 'app' donde están tus modelos y Base.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. Importar tu Base declarativa y los modelos (indirectamente a través de __init__.py)
from app.db.session import Base_CRUD  # Asumo que aquí está definida tu Base para la BD de CRUDs
import app.models  # Esto ejecuta app/models/__init__.py, registrando todos los modelos
# --- FIN SECCIÓN MODIFICADA POR NOSOTROS ---

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# --- INICIO SECCIÓN MODIFICADA POR NOSOTROS ---
target_metadata = Base_CRUD.metadata # 3. Asignar la metadata de tu Base a target_metadata
# --- FIN SECCIÓN MODIFICADA POR NOSOTROS ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url") # Lee la URL de alembic.ini
    context.configure(
        url=url,
        target_metadata=target_metadata, # Usa nuestra target_metadata configurada
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Lee la configuración del engine desde alembic.ini
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata # Usa nuestra target_metadata configurada
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()