import base64
import hashlib

from cryptography.fernet import Fernet

from shared.config import shared_settings


class EncryptionUtility:
    def __init__(self):
        # Hash the encryption key to ensure it is exactly 32 bytes long
        hashed_key = hashlib.sha256(shared_settings.ENCRYPTION_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(hashed_key)
        self.fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        """
        Encrypt the provided data (user ID in this case).
        """
        data = str(data)  # Ensure data is a string to avoid TypeError when hashing
        encrypted_data = self.fernet.encrypt(data.encode())
        return encrypted_data.decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt the provided encrypted data.
        """
        decrypted_data = self.fernet.decrypt(encrypted_data.encode())
        return decrypted_data.decode()
