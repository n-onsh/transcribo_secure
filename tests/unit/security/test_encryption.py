"""
Tests for the encryption service.

Critical aspects:
1. Key management with Azure KeyVault
2. File encryption/decryption
3. Error handling
4. Security boundaries
"""
import pytest
from pathlib import Path
import os
from unittest.mock import MagicMock, patch
from backend.src.services.encryption import EncryptionService

# Test data
TEST_STRING = "test data to encrypt"
TEST_DICT = {"key": "value", "nested": {"key": "value"}}
TEST_BYTES = b"binary data to encrypt"

@pytest.fixture
def encryption_service(mock_azure_keyvault, test_env) -> EncryptionService:
    """Create an encryption service instance with mocked KeyVault."""
    return EncryptionService()

class TestEncryptionService:
    """Test suite for EncryptionService."""

    def test_initialization(self, mock_azure_keyvault, test_env):
        """Test service initialization and key retrieval."""
        service = EncryptionService()
        assert service.fernet is not None
        mock_azure_keyvault.get_secret.assert_called_once()

    def test_string_encryption(self, encryption_service):
        """Test string encryption and decryption."""
        # Encrypt
        encrypted = encryption_service.encrypt_string(TEST_STRING)
        assert encrypted != TEST_STRING
        assert isinstance(encrypted, str)

        # Decrypt
        decrypted = encryption_service.decrypt_string(encrypted)
        assert decrypted == TEST_STRING

    def test_dict_encryption(self, encryption_service):
        """Test dictionary encryption and decryption."""
        # Encrypt
        encrypted = encryption_service.encrypt_dict(TEST_DICT)
        assert encrypted != str(TEST_DICT)
        assert isinstance(encrypted, str)

        # Decrypt
        decrypted = encryption_service.decrypt_dict(encrypted)
        assert decrypted == TEST_DICT

    def test_bytes_encryption(self, encryption_service):
        """Test binary data encryption and decryption."""
        # Encrypt
        encrypted = encryption_service.encrypt_bytes(TEST_BYTES)
        assert encrypted != TEST_BYTES
        assert isinstance(encrypted, bytes)

        # Decrypt
        decrypted = encryption_service.decrypt_bytes(encrypted)
        assert decrypted == TEST_BYTES

    def test_file_encryption(self, encryption_service, temp_dir):
        """Test file encryption and decryption."""
        # Create test file
        input_path = temp_dir / "test.txt"
        encrypted_path = temp_dir / "test.encrypted"
        decrypted_path = temp_dir / "test.decrypted"
        
        input_path.write_bytes(TEST_BYTES)

        # Encrypt file
        encryption_service.encrypt_file(str(input_path), str(encrypted_path))
        assert encrypted_path.exists()
        assert encrypted_path.read_bytes() != TEST_BYTES

        # Decrypt file
        encryption_service.decrypt_file(str(encrypted_path), str(decrypted_path))
        assert decrypted_path.exists()
        assert decrypted_path.read_bytes() == TEST_BYTES

    def test_key_rotation(self, encryption_service, mock_azure_keyvault):
        """Test encryption key rotation."""
        # Encrypt with original key
        encrypted = encryption_service.encrypt_string(TEST_STRING)

        # Rotate key
        encryption_service.rotate_key()
        mock_azure_keyvault.set_secret.assert_called_once()

        # Verify old data can still be decrypted
        decrypted = encryption_service.decrypt_string(encrypted)
        assert decrypted == TEST_STRING

        # Verify new data is encrypted with new key
        new_encrypted = encryption_service.encrypt_string(TEST_STRING)
        assert new_encrypted != encrypted

    def test_metadata_encryption(self, encryption_service):
        """Test selective metadata encryption."""
        metadata = {
            "file_name": "test.mp3",  # Non-sensitive
            "email": "test@example.com",  # Sensitive
            "size": 1024,  # Non-sensitive
            "notes": "confidential",  # Sensitive
        }

        # Encrypt metadata
        encrypted = encryption_service.encrypt_metadata(metadata)

        # Check selective encryption
        assert encrypted["file_name"] == metadata["file_name"]  # Not encrypted
        assert encrypted["size"] == metadata["size"]  # Not encrypted
        assert encrypted["email"] != metadata["email"]  # Encrypted
        assert encrypted["notes"] != metadata["notes"]  # Encrypted

        # Decrypt and verify
        decrypted = encryption_service.decrypt_metadata(encrypted)
        assert decrypted == metadata

    @pytest.mark.parametrize("invalid_data", [
        None,
        "",
        "invalid base64",
        b"invalid bytes",
    ])
    def test_decryption_error_handling(self, encryption_service, invalid_data):
        """Test error handling for invalid encrypted data."""
        with pytest.raises(Exception):
            if isinstance(invalid_data, str):
                encryption_service.decrypt_string(invalid_data)
            else:
                encryption_service.decrypt_bytes(invalid_data)

    def test_key_vault_error_handling(self, test_env):
        """Test handling of KeyVault access errors."""
        with patch("azure.keyvault.secrets.SecretClient") as mock_client:
            # Simulate KeyVault access error
            mock_client.side_effect = Exception("KeyVault access denied")
            
            with pytest.raises(Exception) as exc_info:
                EncryptionService()
            
            assert "KeyVault" in str(exc_info.value)

    def test_file_error_handling(self, encryption_service, temp_dir):
        """Test handling of file operation errors."""
        non_existent = temp_dir / "non_existent.txt"
        output = temp_dir / "output.txt"

        with pytest.raises(Exception):
            encryption_service.encrypt_file(str(non_existent), str(output))

        with pytest.raises(Exception):
            encryption_service.decrypt_file(str(non_existent), str(output))

    def test_stream_encryption(self, encryption_service, temp_dir):
        """Test stream encryption and decryption."""
        from io import BytesIO
        
        # Create test stream
        stream = BytesIO(TEST_BYTES)
        
        # Encrypt stream
        encrypted = encryption_service.encrypt_stream(stream)
        assert encrypted != TEST_BYTES
        assert isinstance(encrypted, bytes)
        
        # Decrypt stream
        decrypt_stream = BytesIO(encrypted)
        decrypted = encryption_service.decrypt_stream(decrypt_stream)
        assert decrypted == TEST_BYTES

    def test_invalid_key_handling(self, encryption_service):
        """Test handling of invalid encryption keys."""
        # Save original key
        original_key = encryption_service.fernet.key
        
        # Test with invalid key
        try:
            from cryptography.fernet import Fernet
            invalid_key = Fernet.generate_key()
            encryption_service.fernet = Fernet(invalid_key)
            
            # Try to decrypt data encrypted with original key
            encrypted = encryption_service.encrypt_string(TEST_STRING)
            encryption_service.fernet = Fernet(original_key)  # Restore original key
            
            with pytest.raises(Exception):
                encryption_service.decrypt_string(encrypted)
        finally:
            # Restore original key
            encryption_service.fernet = Fernet(original_key)

    def test_concurrent_operations(self, encryption_service):
        """Test concurrent encryption operations."""
        import concurrent.futures
        import random
        
        def encrypt_random():
            data = TEST_STRING + str(random.randint(1, 1000))
            encrypted = encryption_service.encrypt_string(data)
            decrypted = encryption_service.decrypt_string(encrypted)
            return data == decrypted
        
        # Run multiple encryption operations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: encrypt_random(), range(10)))
        
        assert all(results)

    def test_large_data_handling(self, encryption_service, temp_dir):
        """Test encryption of large data."""
        # Create large test data (10MB)
        large_data = os.urandom(10 * 1024 * 1024)
        
        # Test string encryption (base64 encoded)
        import base64
        large_string = base64.b64encode(large_data).decode()
        encrypted_string = encryption_service.encrypt_string(large_string)
        decrypted_string = encryption_service.decrypt_string(encrypted_string)
        assert decrypted_string == large_string
        
        # Test file encryption
        input_path = temp_dir / "large_test.bin"
        encrypted_path = temp_dir / "large_test.encrypted"
        decrypted_path = temp_dir / "large_test.decrypted"
        
        input_path.write_bytes(large_data)
        encryption_service.encrypt_file(str(input_path), str(encrypted_path))
        encryption_service.decrypt_file(str(encrypted_path), str(decrypted_path))
        assert decrypted_path.read_bytes() == large_data

    def test_error_boundary_conditions(self, encryption_service):
        """Test error handling for boundary conditions."""
        # Test empty data
        with pytest.raises(Exception):
            encryption_service.encrypt_string("")
        
        # Test None input
        with pytest.raises(Exception):
            encryption_service.encrypt_string(None)
        
        # Test very large dictionary
        large_dict = {"key" + str(i): "x" * 1000 for i in range(1000)}
        encrypted_dict = encryption_service.encrypt_dict(large_dict)
        decrypted_dict = encryption_service.decrypt_dict(encrypted_dict)
        assert decrypted_dict == large_dict
        
        # Test invalid UTF-8 in string
        invalid_utf8 = "test \xff data"
        with pytest.raises(Exception):
            encryption_service.encrypt_string(invalid_utf8)

    def test_key_validation(self, encryption_service):
        """Test encryption key validation."""
        # Test key length validation
        with pytest.raises(Exception):
            from cryptography.fernet import Fernet
            invalid_key = b"too short key"
            encryption_service.fernet = Fernet(base64.urlsafe_b64encode(invalid_key))
        
        # Test key format validation
        with pytest.raises(Exception):
            encryption_service.fernet = Fernet(b"invalid key format")
        
        # Test key rotation validation
        original_key = encryption_service.fernet.key
        try:
            # Simulate invalid key in vault
            with patch.object(encryption_service.key_vault, 'get_secret') as mock_get:
                mock_get.return_value.value = "invalid-key"
                with pytest.raises(Exception):
                    encryption_service._init_encryption()
        finally:
            # Restore original key
            encryption_service.fernet = Fernet(original_key)
