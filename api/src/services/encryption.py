from azure.keyvault.keys import KeyClient
from azure.keyvault.keys.crypto import CryptographyClient
from azure.identity import DefaultAzureCredential
import os
import base64
from typing import Union

class EncryptionService:
    def __init__(self):
        # Initialize Azure Key Vault client
        credential = DefaultAzureCredential()
        key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
        self.key_client = KeyClient(vault_url=key_vault_url, credential=credential)
        
        # Get or create encryption key
        key_name = "transcribo-storage-key"
        try:
            key = self.key_client.get_key(key_name)
        except Exception:
            key = self.key_client.create_rsa_key(key_name, size=2048)
        
        # Initialize crypto client
        self.crypto_client = CryptographyClient(key=key, credential=credential)

    async def encrypt_data(self, data: Union[bytes, str]) -> bytes:
        """Encrypt data using Azure Key Vault"""
        if isinstance(data, str):
            data = data.encode()
            
        result = self.crypto_client.encrypt("RSA1_5", data)
        return base64.b64encode(result.ciphertext)

    async def decrypt_data(self, encrypted_data: Union[bytes, str]) -> bytes:
        """Decrypt data using Azure Key Vault"""
        if isinstance(encrypted_data, str):
            encrypted_data = encrypted_data.encode()
            
        encrypted_data = base64.b64decode(encrypted_data)
        result = self.crypto_client.decrypt("RSA1_5", encrypted_data)
        return result.plaintext