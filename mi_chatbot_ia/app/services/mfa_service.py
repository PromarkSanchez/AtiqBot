# app/services/mfa_service.py
import pyotp # type: ignore
import qrcode # type: ignore
import io # Para manejar la imagen QR en memoria
import base64 # Para convertir la imagen QR a data URL base64
from typing import Tuple, Optional

from app.config import settings # Para MFA_APP_NAME

class MFAService:
    def __init__(self, app_name: Optional[str] = None):
        self.app_name = app_name or settings.MFA_APP_NAME
        if not self.app_name:
            # En una app real, podrías querer que esto sea un error de configuración si no se provee
            print("ADVERTENCIA MFA_SERVICE: MFA_APP_NAME no configurado, se usará un default genérico.")
            self.app_name = "MyApp" 

    def generate_new_mfa_details(self, username_for_uri: str) -> Tuple[str, str]:
        """
        Genera un nuevo secreto MFA (compatible con Google Authenticator/Authy etc.)
        y la URL otpauth:// correspondiente para el código QR.

        Args:
            username_for_uri: El identificador del usuario (ej. email, DNI, o username_ad)
                              que se mostrará en la app autenticadora.

        Returns:
            Una tupla conteniendo (secret_base32, otpauth_url_str)
        """
        # Generar un secreto base32 seguro (pyotp usa 16 bytes por defecto, que son 32 caracteres base32)
        # Puedes aumentar los bytes si quieres un secreto más largo, ej. pyotp.random_base32(32) para 32 bytes
        mfa_secret_base32 = pyotp.random_base32() 
        
        totp_instance = pyotp.TOTP(mfa_secret_base32)
        
        # Crear la URL otpauth (formato estándar para apps TOTP)
        # issuer_name es el nombre de tu aplicación/organización.
        # name es el identificador de la cuenta, usualmente el email o username.
        otpauth_url_str = totp_instance.provisioning_uri(
            name=username_for_uri, 
            issuer_name=self.app_name
        )
        
        # No loguear el secreto en producción. Solo para debug si es necesario.
        print(f"MFA_SERVICE: Secreto y OTPAuth URL generados para '{username_for_uri}'.")
        # print(f"  DEBUG Secreto (NO LOGUEAR EN PROD): {mfa_secret_base32}")
        # print(f"  DEBUG OTPAuth URL: {otpauth_url_str}")
        
        return mfa_secret_base32, otpauth_url_str

    def verify_mfa_code(self, mfa_secret_base32_for_user: str, code_from_user: str) -> bool:
        """
        Verifica un código TOTP (ingresado por el usuario) contra el secreto almacenado para ese usuario.

        Args:
            mfa_secret_base32_for_user: El secreto MFA (en formato base32) asociado al usuario.
                                       Este es el secreto que fue guardado (encriptado) en la BD.
            code_from_user: El código de 6 dígitos que el usuario ingresó desde su app autenticadora.

        Returns:
            True si el código es válido dentro de la ventana de tiempo, False en caso contrario.
        """
        if not mfa_secret_base32_for_user or not code_from_user:
            print("MFA_SERVICE: Secreto o código no proporcionados para verificación.")
            return False
            
        totp_instance = pyotp.TOTP(mfa_secret_base32_for_user)
        
        try:
            # pyotp.TOTP.verify() compara el token con el valor actual y ventanas pasadas/futuras
            # (por defecto, 1 ventana hacia atrás y 1 hacia adelante, cada ventana es de 30s).
            # Puedes ajustar la ventana si es necesario: totp_instance.verify(code_from_user, window=X)
            is_valid = totp_instance.verify(code_from_user)
            
            if is_valid:
                print(f"MFA_SERVICE: Código TOTP '{code_from_user}' VERIFICADO EXITOSAMENTE.")
            else:
                print(f"MFA_SERVICE: Código TOTP '{code_from_user}' INVÁLIDO.")
            return is_valid
            
        except Exception as e:
            # Esto podría ocurrir si el secreto no es base32 válido o el token tiene formato incorrecto.
            print(f"MFA_SERVICE: Error durante la verificación del código TOTP: {e}")
            traceback.print_exc() # type: ignore
            return False

    def generate_qr_code_image_data_url(self, otpauth_url: str) -> Optional[str]:
        """
        Genera una imagen de código QR como Data URL (base64) a partir de la otpauth_url.
        Esto es útil si el backend necesita servir la imagen QR directamente.

        Args:
            otpauth_url: La URL otpauth:// completa (ej. "otpauth://totp/MiApp:usuario@ejemplo.com?secret=JBSWY3DPEHPK3PXP&issuer=MiApp")

        Returns:
            Un string Data URL (ej. "data:image/png;base64,iVBORw0KGgo...") o None si hay un error.
        """
        if not otpauth_url:
            return None
        try:
            # Crear la imagen QR en memoria
            img = qrcode.make(otpauth_url) # qrcode.make() devuelve un objeto de imagen PIL por defecto
            
            # Guardar la imagen en un buffer de bytes en formato PNG
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG') # Guardar como PNG
            img_byte_arr = img_byte_arr.getvalue() # Obtener los bytes
            
            # Convertir los bytes de la imagen a una cadena base64
            base64_image_str = base64.b64encode(img_byte_arr).decode('utf-8')
            
            # Crear el Data URL
            data_url = f"data:image/png;base64,{base64_image_str}"
            return data_url
            
        except Exception as e:
            print(f"MFA_SERVICE: Error generando QR Code Data URL: {e}")
            traceback.print_exc() # type: ignore
            return None

# Ejemplo de uso (para prueba local si ejecutas este archivo)
if __name__ == '__main__':
    print("--- Probando MFAService ---")
    mfa_service_instance = MFAService(app_name="MiChatbotAdminPanel") # Sobrescribe el de settings para prueba
    
    test_username = "usuario.prueba@midominio.com"
    
    # 1. Generar secreto y URL
    secret, otp_url = mfa_service_instance.generate_new_mfa_details(test_username)
    print(f"Usuario: {test_username}")
    print(f"Secreto Base32 Generado (NO GUARDAR ASÍ EN PROD, ENCRIPTARLO): {secret}")
    print(f"OTPAuth URL (para QR): {otp_url}")
    
    # 2. Generar QR (Opcional, si quieres ver la imagen o Data URL)
    qr_data_url = mfa_service_instance.generate_qr_code_image_data_url(otp_url)
    if qr_data_url:
        print(f"QR Code Data URL (primeros 100 chars): {qr_data_url[:100]}...")
        # Podrías guardar esto en un archivo .html para verlo:
        # with open("qr_test.html", "w") as f:
        #     f.write(f"<img src='{qr_data_url}' alt='QR Code Setup MFA' />")
        # print("QR Code guardado en qr_test.html (abrir en navegador para escanear).")
    else:
        print("No se pudo generar el Data URL del QR Code.")

    # 3. Simular verificación (necesitarás escanear el QR con Google Auth y obtener un código)
    if secret: # Solo si se generó secreto
        print("\n--- Simulación de Verificación ---")
        print(f"Escanea el QR (o usa la OTPAuth URL en tu app autenticadora) para el secreto: {secret}")
        print("Luego, ingresa el código de 6 dígitos que muestra tu app:")
        
        try:
            current_otp_code = input("Ingresa el código TOTP de 6 dígitos: ")
            if len(current_otp_code) == 6 and current_otp_code.isdigit():
                is_code_valid = mfa_service_instance.verify_mfa_code(secret, current_otp_code)
                if is_code_valid:
                    print("¡FELICIDADES! El código TOTP ingresado es VÁLIDO.")
                else:
                    print("FALLO: El código TOTP ingresado es INVÁLIDO o ha expirado.")
            else:
                print("Entrada inválida. Se esperaba un código de 6 dígitos.")
        except KeyboardInterrupt:
            print("\nPrueba de verificación cancelada.")
        except Exception as e_input:
            print(f"Error durante input de prueba: {e_input}")