# app/utils/security_utils.py
from cryptography.fernet import Fernet # type: ignore
from app.config import settings # Importar tus settings de FastAPI
import traceback # Importar traceback
from typing import Optional, List, Any

_fernet_instance: Optional[Fernet] = None # type: ignore

from passlib.context import CryptContext

# Creamos una única instancia de CryptContext.
# Le decimos que el algoritmo por defecto es bcrypt.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña en texto plano contra su versión hasheada."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashea una contraseña en texto plano para guardarla en la base de datos."""
    return pwd_context.hash(password)



def get_fernet() -> Fernet:
    """Inicializa y devuelve la instancia de Fernet usando la clave de settings."""
    global _fernet_instance
    if _fernet_instance is None:
        if not settings.FERNET_KEY:
            # Este error es más informativo en el contexto de la aplicación.
            print("ERROR CRÍTICO (security_utils): FERNET_KEY no está configurada en app.config.settings.")
            raise ValueError("La clave de encriptación (FERNET_KEY) no está configurada en la aplicación.")
        try:
            key_bytes = settings.FERNET_KEY.encode()
            _fernet_instance = Fernet(key_bytes)
        except Exception as e:
            print(f"ERROR CRÍTICO (security_utils): Fallo al inicializar Fernet con la clave proporcionada: {e}")
            raise ValueError(f"FERNET_KEY inválida o problema al inicializar Fernet: {e}")
    return _fernet_instance

def encrypt_data(data_str: str) -> str:
    """Encripta un string usando la instancia Fernet global."""
    if not data_str:
        return "" # O podrías devolver None o lanzar un error si el input vacío no es esperado
    try:
        f = get_fernet()
        encrypted_bytes = f.encrypt(data_str.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e_enc:
        print(f"ERROR (security_utils): Encriptando datos - {e_enc}")
        traceback.print_exc()
        raise # Relanzar la excepción para que el llamador la maneje o loguee un error grave.

def decrypt_data(encrypted_data_str: str) -> str:
    """Desencripta un string usando la instancia Fernet global."""
    if not encrypted_data_str:
        return "" # O devolver None o error
    try:
        f = get_fernet()
        decrypted_bytes = f.decrypt(encrypted_data_str.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e_dec: # Puede ser InvalidToken, etc.
        print(f"ERROR (security_utils): Desencriptando datos (¿clave incorrecta, datos corruptos?): {e_dec}")
        # Devolver un indicador de error en lugar de la traza completa
        return "[DATO ENCRIPTADO INVÁLIDO O ERROR DE DESENCRIPTACIÓN]"