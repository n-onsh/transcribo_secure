"""Hash verification utilities."""

import hashlib
import os
from typing import Dict, Optional
from ..utils.logging import log_info, log_error

def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """Calculate hash for a file."""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    except Exception as e:
        log_error(f"Error calculating hash for {file_path}: {str(e)}")
        raise

def calculate_data_hash(data: bytes, algorithm: str = 'sha256') -> str:
    """Calculate hash for binary data."""
    try:
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(data)
        return hash_obj.hexdigest()
    except Exception as e:
        log_error(f"Error calculating hash for data: {str(e)}")
        raise

def verify_file_hash(file_path: str, expected_hash: str, algorithm: str = 'sha256') -> bool:
    """Verify file hash matches expected hash."""
    try:
        actual_hash = calculate_file_hash(file_path, algorithm)
        return actual_hash == expected_hash
    except Exception as e:
        log_error(f"Error verifying hash for {file_path}: {str(e)}")
        return False

def verify_data_hash(data: bytes, expected_hash: str, algorithm: str = 'sha256') -> bool:
    """Verify data hash matches expected hash."""
    try:
        actual_hash = calculate_data_hash(data, algorithm)
        return actual_hash == expected_hash
    except Exception as e:
        log_error(f"Error verifying hash for data: {str(e)}")
        return False

class HashVerificationError(Exception):
    """Exception raised when hash verification fails."""
    pass
