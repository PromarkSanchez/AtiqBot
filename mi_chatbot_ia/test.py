from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv() # Para cargar FERNET_KEY de .env

FERNET_KEY_STR_FROM_ENV = os.getenv("FERNET_KEY")
if not FERNET_KEY_STR_FROM_ENV:
    raise ValueError("FERNET_KEY no está en .env o no se cargó")

fernet_instance = Fernet(FERNET_KEY_STR_FROM_ENV.encode())

# !! REEMPLAZA ESTO CON LA CONTRASEÑA REAL DE 'sa2' !!
password_real_de_sa2 = "erf$sedSQW" 

if password_real_de_sa2 == "TuPasswordRealPara_sa2":
    print("POR FAVOR, EDITA EL SCRIPT Y PON LA CONTRASEÑA REAL DE 'sa2'")
else:
    encrypted_password_bytes = fernet_instance.encrypt(password_real_de_sa2.encode())
    encrypted_password_str = encrypted_password_bytes.decode()
    print(f"La contraseña '{password_real_de_sa2}' encriptada con tu FERNET_KEY actual es:")
    print(encrypted_password_str)
    print("\nCopia este valor encriptado y actualiza la columna 'encrypted_password' "
          "en tu tabla 'db_connection_configs' para la conexión 'DW Produccion SQL Server'.")