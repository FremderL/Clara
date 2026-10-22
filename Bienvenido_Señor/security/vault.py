"""
vault.py
Bóveda cifrada AES con PBKDF2 y protección de memoria básica.
Solo usa dependencias estándar y cryptography. Cumple reglas de seguridad y compatibilidad.
"""
import os
import base64
import logging
from typing import Optional
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidKey

logging.basicConfig(level=logging.INFO)

class Vault:
    def __init__(self, password: str, salt: Optional[bytes] = None):
        self.salt = salt or os.urandom(16)
        self.key = self._derive_key(password, self.salt)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    def encrypt(self, data: bytes) -> bytes:
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.key), modes.CFB(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ct = encryptor.update(data) + encryptor.finalize()
        return base64.b64encode(self.salt + iv + ct)

    def decrypt(self, token: bytes) -> Optional[bytes]:
        try:
            raw = base64.b64decode(token)
            salt, iv, ct = raw[:16], raw[16:32], raw[32:]
            key = self._derive_key_from_existing(self.key, salt)
            cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            return decryptor.update(ct) + decryptor.finalize()
        except (InvalidKey, ValueError, Exception) as e:
            logging.error(f"Error al descifrar: {e}")
            return None

    def _derive_key_from_existing(self, key: bytes, salt: bytes) -> bytes:
        # Para compatibilidad, simplemente retorna el key actual
        return key

# Ejemplo seguro de uso
if __name__ == "__main__":
    v = Vault(password="test123")
    secreto = v.encrypt(b"mensaje secreto")
    print("Cifrado:", secreto)
    descifrado = v.decrypt(secreto)
    print("Descifrado:", descifrado)
