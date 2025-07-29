# app/api/user_endpoints.py
# app/api/user_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from sqlalchemy.future import select # type: ignore # <--- ¡AÑADE ESTA LÍNEA!
from typing import List

 
from app.db.session import get_crud_db_session # <--- CORREGIDO
from app.schemas.schemas import UserCreate, UserResponse # Schemas para entrada y salida
from app.crud import crud_user # Importamos nuestros helpers CRUD

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"]
)

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_in: UserCreate, # Datos del usuario vienen en el body del request
    db: AsyncSession = Depends(get_crud_db_session) # Inyecta la sesión de BD
):
    """
    Crea un nuevo usuario.
    """
    # Verificar si el DNI ya existe
    existing_user = await crud_user.get_user_by_dni(db=db, dni=user_in.dni)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El DNI '{user_in.dni}' ya está registrado."
        )
    # Si el email es provisto, verificar si ya existe (si la lógica de negocio lo requiere)
    if user_in.email:
        existing_email = await db.execute(
            select(crud_user.UserModel).filter(crud_user.UserModel.email == user_in.email)
        )
        if existing_email.scalars().first():
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El email '{user_in.email}' ya está registrado."
            )

    new_user = await crud_user.create_user(db=db, user_in=user_in)
    return new_user # Pydantic automáticamente convertirá el UserModel a UserResponse


@router.get("/{user_id}", response_model=UserResponse)
async def read_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_crud_db_session)
):
    """
    Obtiene un usuario por su ID.
    """
    db_user = await crud_user.get_user_by_id(db=db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return db_user

@router.get("/", response_model=List[UserResponse])
async def read_users(
    skip: int = 0,
    limit: int = 101,
    db: AsyncSession = Depends(get_crud_db_session)
):
    """
    Obtiene una lista de usuarios (paginada).
    """
    users = await crud_user.get_users(db=db, skip=skip, limit=limit)
    return users

# Aquí podríamos añadir endpoints para PUT (actualizar) y DELETE si los necesitamos inmediatamente.
# Los helpers CRUD ya están listos.