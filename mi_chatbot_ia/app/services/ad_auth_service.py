# app/services/ad_auth_service.py
from ldap3 import Server, Connection, ALL, NTLM, SUBTREE, SASL, KERBEROS, strategy # type: ignore # strategy sin acento
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError, LDAPCommunicationError, LDAPException # type: ignore
from ldap3.utils.conv import escape_filter_chars # type: ignore # Importación correcta
from typing import Optional, Dict, Any, List
import traceback

from app.config import settings

class ADAuthService:
    def __init__(self):
        if not settings.AD_SERVER_URL or not settings.AD_BASE_DN:
            print("ERROR AD_AUTH_SERVICE: AD_SERVER_URL y/o AD_BASE_DN no configurados.")
            raise ValueError("Configuración de AD incompleta en settings.")
        
        self.server_url: str = settings.AD_SERVER_URL
        self.base_dn: str = settings.AD_BASE_DN
        self.upn_suffix: Optional[str] = settings.AD_UPN_SUFFIX # Ej: "upch.edu.pe"
        self.domain_nt: Optional[str] = settings.AD_DOMAIN_NT # Ej: "upchnt"
        self.ad_username_attr_to_store: str = settings.AD_USERNAME_AD_ATTRIBUTE_TO_STORE # Ej: "sAMAccountName"
        self.timeout: int = settings.AD_TIMEOUT_SECONDS
        
        self.attributes_to_fetch: List[str] = [
            "sAMAccountName", "userPrincipalName", "mail", 
            "displayName", "givenName", "sn", "cn"
        ]
        # --- MÉTODO NUEVO ---
    def validate_credentials(self, dni_as_username_input: str, password: str) -> bool:
        """
        Una función simple que solo valida credenciales y devuelve True/False.
        Ideal para nuestra lógica de autenticación unificada.
        """
        attributes = self.authenticate_user_and_get_attributes(dni_as_username_input, password)
        return attributes is not None
    # ------------------

    def _try_bind_and_get_attributes(
        self, 
        user_identifier_for_bind: str, # Esto será el UPN completo o el DOMINIO\username
        password: str
    ) -> Optional[Dict[str, Any]]:
        server = Server(self.server_url, get_info=ALL, connect_timeout=self.timeout)
        conn: Optional[Connection] = None
        
        try:
            print(f"    AD_SERVICE: Intentando bind con servidor '{self.server_url}' usando ID para bind: '{user_identifier_for_bind}'")
            # Usar la conexión simple. ldap3 es síncrono por defecto.
            conn = Connection(server, user=user_identifier_for_bind, password=password, auto_bind=True, raise_exceptions=False) 
            
            if conn.bound:
                print(f"    AD_SERVICE: Bind exitoso para '{user_identifier_for_bind}'. Buscando atributos...")
                
                # Determinar el filtro de búsqueda basado en el identificador de bind.
                # El filtro busca por el atributo que corresponde al identificador usado para el bind exitoso.
                # Si el bind se hizo con UPN (user@domain.com), entonces el filtro debe ser userPrincipalName.
                # Si el bind se hizo con sAMAccountName (o DOMAIN\user que mapea a sAMAccountName), el filtro es sAMAccountName.
                
                # Para la BÚSQUEDA, usamos el username "limpio" (sin prefijo de dominio si se usó DOMAIN\user)
                # o el UPN completo.
                search_value_for_filter = user_identifier_for_bind
                attribute_for_filter = "userPrincipalName" # Asumir UPN por defecto

                if "@" not in user_identifier_for_bind and self.domain_nt and user_identifier_for_bind.startswith(self.domain_nt + "\\"):
                    # Fue un bind DOMAIN\user, buscar por sAMAccountName usando solo la parte del user
                    search_value_for_filter = user_identifier_for_bind.split("\\", 1)[1]
                    attribute_for_filter = "sAMAccountName"
                elif "@" not in user_identifier_for_bind : # No es UPN ni DOMAIN\user, probablemente solo el sAMAccountName
                    attribute_for_filter = "sAMAccountName"


                search_filter = f"({attribute_for_filter}={escape_filter_chars(search_value_for_filter)})"

                print(f"    AD_SERVICE: Usando filtro de búsqueda: '{search_filter}' en Base DN: '{self.base_dn}'")
                conn.search(
                    search_base=self.base_dn,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=self.attributes_to_fetch
                )

                if conn.entries:
                    user_entry = conn.entries[0]
                    user_attributes = {
                        attr: user_entry[attr].value if user_entry[attr] and user_entry[attr].values else None 
                        for attr in self.attributes_to_fetch if attr in user_entry
                    }
                    for key, value_list_or_val in user_attributes.items(): # Normalizar listas a primer elemento
                        if isinstance(value_list_or_val, list) and value_list_or_val:
                            user_attributes[key] = value_list_or_val[0]

                    print(f"    AD_SERVICE: Atributos recuperados: { {k: (str(v)[:30]+'...' if isinstance(v,str) and len(str(v))>30 else v) for k,v in user_attributes.items()} }")
                    conn.unbind()
                    return user_attributes
                else: 
                    print(f"    AD_SERVICE: Bind exitoso para '{user_identifier_for_bind}', pero la búsqueda con filtro '{search_filter}' no devolvió entradas. Resultado LDAP de la búsqueda: {conn.result}")
                    conn.unbind()
                    return None 

            else: 
                print(f"    AD_SERVICE: Falló el bind para '{user_identifier_for_bind}'. Resultado LDAP: {conn.result}")
                if conn and conn.result and isinstance(conn.result, dict) and 'description' in conn.result and 'result' in conn.result:
                    print(f"      Detalle LDAP: {conn.result['description']} (Código: {conn.result['result']})")
                if conn: conn.unbind() # ldap3 >=2.9: es seguro llamar unbind() incluso si bind() falló o no se llamó
                return None
        except LDAPSocketOpenError:
            print(f"    AD_SERVICE: ERROR - No se pudo conectar al servidor LDAP: {self.server_url}")
        except LDAPCommunicationError as e:
            print(f"    AD_SERVICE: ERROR de comunicación LDAP: {e}")
        except LDAPException as e_ldap: 
            print(f"    AD_SERVICE: Excepción LDAP genérica para '{user_identifier_for_bind}': {e_ldap}")
        except Exception as e_general: 
            print(f"    AD_SERVICE: Error general inesperado durante bind/búsqueda para '{user_identifier_for_bind}': {type(e_general).__name__} - {e_general}")
            traceback.print_exc()
        finally:
            if conn and conn.bound: 
                conn.unbind()
        return None

    def authenticate_user_and_get_attributes(self, dni_as_username_input: str, password: str) -> Optional[Dict[str, Any]]:
        if not dni_as_username_input or not password:
            print("AD_SERVICE: DNI de input o contraseña no proporcionados para autenticación.")
            return None
        
        user_attributes_found: Optional[Dict[str, Any]] = None # Renombrado para claridad

        # --- Intento 1: User Principal Name (UPN) ---
        constructed_upn_to_try: Optional[str] = None
        if self.upn_suffix:
            # Construir UPN: dni@sufijo.com
            # Asumiendo que upn_suffix es solo "dominio.com" y no "@dominio.com"
            if self.upn_suffix.startswith("@"):
                constructed_upn_to_try = f"{dni_as_username_input}{self.upn_suffix}"
            else:
                constructed_upn_to_try = f"{dni_as_username_input}@{self.upn_suffix}"
            
            print(f"AD_SERVICE: Intentando autenticación AD para DNI '{dni_as_username_input}' como UPN: '{constructed_upn_to_try}'")
            user_attributes_found = self._try_bind_and_get_attributes(constructed_upn_to_try, password)
            if user_attributes_found:
                user_attributes_found["used_bind_identifier_type"] = "UPN"
                user_attributes_found["bind_dn_or_principal_used"] = constructed_upn_to_try
                # Asegurar que el atributo clave para AppUser.username_ad (el DNI) esté presente
                if self.ad_username_attr_to_store not in user_attributes_found or not user_attributes_found[self.ad_username_attr_to_store]:
                    # Si el DNI es el sAMAccountName y es el atributo a almacenar, y no vino con ese nombre:
                    if self.ad_username_attr_to_store.lower() == "samaccountname":
                        user_attributes_found[self.ad_username_attr_to_store] = dni_as_username_input 
                print(f"AD_SERVICE: Autenticación con UPN exitosa para DNI '{dni_as_username_input}'.")
                return user_attributes_found

        # --- Intento 2: DOMAIN\user (sAMAccountName) ---
        constructed_domain_user_to_try: Optional[str] = None
        if self.domain_nt: # Solo si tenemos un dominio NT configurado
            constructed_domain_user_to_try = self.domain_nt + "\\" + dni_as_username_input # DOMAIN\DNI
            print(f"AD_SERVICE: Autenticación UPN falló o no configurada. Intentando como DOMAIN\\USER: '{constructed_domain_user_to_try}'")
            user_attributes_found = self._try_bind_and_get_attributes(constructed_domain_user_to_try, password)
            if user_attributes_found:
                user_attributes_found["used_bind_identifier_type"] = "DOMAIN_USER"
                user_attributes_found["bind_dn_or_principal_used"] = constructed_domain_user_to_try
                if self.ad_username_attr_to_store.lower() == "samaccountname" and \
                   (self.ad_username_attr_to_store not in user_attributes_found or not user_attributes_found[self.ad_username_attr_to_store]):
                    user_attributes_found[self.ad_username_attr_to_store] = dni_as_username_input
                print(f"AD_SERVICE: Autenticación con DOMAIN\\USER exitosa para DNI '{dni_as_username_input}'.")
                return user_attributes_found
        
        print(f"AD_SERVICE: Autenticación AD falló para DNI '{dni_as_username_input}' con todos los formatos aplicables.")
        return None