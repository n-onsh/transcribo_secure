"""Local secrets store for development."""

import os
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import KeyVaultError
from ..types import ErrorContext

class LocalSecretsStore:
    """File-based secrets store for local development."""

    def __init__(self, secrets_path: str):
        """Initialize store.
        
        Args:
            secrets_path: Path to secrets directory
        """
        self.secrets_path = Path(secrets_path)
        self.secrets_file = self.secrets_path / "secrets.json"
        self.secrets: Dict[str, Dict[str, Any]] = {}
        
        # Ensure secrets directory exists
        self.secrets_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing secrets
        self._load_secrets()

    def _load_secrets(self) -> None:
        """Load secrets from file."""
        try:
            if self.secrets_file.exists():
                with open(self.secrets_file, "r") as f:
                    self.secrets = json.load(f)
            else:
                self.secrets = {}
                self._save_secrets()
                
            log_info("Loaded secrets from local store", {
                "path": str(self.secrets_file),
                "count": len(self.secrets)
            })

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "load_secrets",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "path": str(self.secrets_file)
                }
            }
            log_error(f"Failed to load secrets: {str(e)}")
            raise KeyVaultError(
                "Failed to load secrets from local store",
                details=error_context
            )

    def _save_secrets(self) -> None:
        """Save secrets to file."""
        try:
            # Create backup of existing file
            if self.secrets_file.exists():
                backup_file = self.secrets_path / f"secrets.{datetime.utcnow().timestamp()}.bak"
                with open(self.secrets_file, "r") as src, open(backup_file, "w") as dst:
                    dst.write(src.read())

            # Write new secrets
            with open(self.secrets_file, "w") as f:
                json.dump(self.secrets, f, indent=2)

            log_info("Saved secrets to local store", {
                "path": str(self.secrets_file),
                "count": len(self.secrets)
            })

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "save_secrets",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "path": str(self.secrets_file)
                }
            }
            log_error(f"Failed to save secrets: {str(e)}")
            raise KeyVaultError(
                "Failed to save secrets to local store",
                details=error_context
            )

    def get_secret(self, name: str) -> Optional[str]:
        """Get a secret.
        
        Args:
            name: Secret name
            
        Returns:
            Secret value if found, None otherwise
        """
        try:
            secret = self.secrets.get(name)
            if not secret:
                return None
                
            # Check expiration
            if "expires_on" in secret:
                expires = datetime.fromisoformat(secret["expires_on"])
                if datetime.utcnow() > expires:
                    # Secret expired
                    del self.secrets[name]
                    self._save_secrets()
                    return None
                    
            return secret["value"]

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get_secret",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "secret_name": name
                }
            }
            log_error(f"Failed to get secret {name}: {str(e)}")
            raise KeyVaultError(
                f"Failed to get secret: {str(e)}",
                details=error_context
            )

    def set_secret(
        self,
        name: str,
        value: str,
        content_type: Optional[str] = None,
        enabled: bool = True,
        expires_on: Optional[datetime] = None
    ) -> None:
        """Set a secret.
        
        Args:
            name: Secret name
            value: Secret value
            content_type: Optional content type
            enabled: Whether secret is enabled
            expires_on: Optional expiration time
        """
        try:
            self.secrets[name] = {
                "value": value,
                "content_type": content_type,
                "enabled": enabled,
                "created_on": datetime.utcnow().isoformat(),
                "updated_on": datetime.utcnow().isoformat()
            }
            
            if expires_on:
                self.secrets[name]["expires_on"] = expires_on.isoformat()
                
            self._save_secrets()

            log_info(f"Set secret {name}")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "set_secret",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "secret_name": name
                }
            }
            log_error(f"Failed to set secret {name}: {str(e)}")
            raise KeyVaultError(
                f"Failed to set secret: {str(e)}",
                details=error_context
            )

    def delete_secret(self, name: str) -> None:
        """Delete a secret.
        
        Args:
            name: Secret name
        """
        try:
            if name in self.secrets:
                del self.secrets[name]
                self._save_secrets()
                log_info(f"Deleted secret {name}")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "delete_secret",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "secret_name": name
                }
            }
            log_error(f"Failed to delete secret {name}: {str(e)}")
            raise KeyVaultError(
                f"Failed to delete secret: {str(e)}",
                details=error_context
            )
