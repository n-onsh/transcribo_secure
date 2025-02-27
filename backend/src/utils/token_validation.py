"""Token validation utilities."""

import jwt
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from jwt import PyJWTError
import requests
from fastapi import HTTPException
from .logging import log_info, log_error, log_warning
from .metrics import (
    AUTH_OPERATIONS,
    AUTH_ERRORS,
    AUTH_LATENCY,
    track_auth_operation,
    track_auth_latency,
    track_auth_error
)
from .exceptions import AuthenticationError, ConfigurationError
from ..config import config

class TokenValidator:
    """Token validator for Azure AD tokens."""

    def __init__(self):
        """Initialize token validator with caching."""
        try:
            # Get Azure AD configuration
            self.tenant_id = config.auth.azure_tenant_id
            self.client_id = config.auth.azure_client_id
            
            if not all([self.tenant_id, self.client_id]):
                raise ConfigurationError("Missing required Azure AD configuration")
            
            # OpenID configuration URL
            self.config_url = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0/.well-known/openid-configuration"
            
            # Cache for JWKS with expiration
            self.jwks: Optional[Dict[str, Any]] = None
            self.jwks_uri: Optional[str] = None
            self.jwks_last_updated: Optional[datetime] = None
            self.jwks_cache_duration = timedelta(hours=24)  # Cache for 24 hours
            
            # Initialize
            self._load_openid_config()
            log_info("Token validator initialized", {
                "tenant_id": self.tenant_id,
                "config_url": self.config_url
            })

        except Exception as e:
            log_error("Failed to initialize token validator", {"error": str(e)})
            raise

    def _load_openid_config(self) -> None:
        """Load OpenID configuration."""
        try:
            # Track operation
            track_auth_operation('load_config')
            start_time = datetime.utcnow()

            # Get OpenID configuration
            response = requests.get(self.config_url)
            response.raise_for_status()
            config = response.json()
            
            # Get JWKS URI
            self.jwks_uri = config["jwks_uri"]
            
            # Load JWKS
            self._load_jwks()
            
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_auth_latency(duration)

        except Exception as e:
            track_auth_error()
            log_error("Failed to load OpenID config", {
                "error": str(e),
                "config_url": self.config_url
            })
            raise ConfigurationError(
                "Failed to load Azure AD configuration. Check:\n"
                "1. Network connectivity\n"
                "2. Azure AD tenant configuration\n"
                f"Original error: {str(e)}"
            )

    def _should_refresh_jwks(self) -> bool:
        """Check if JWKS should be refreshed."""
        if not self.jwks or not self.jwks_last_updated:
            return True
            
        return datetime.utcnow() - self.jwks_last_updated > self.jwks_cache_duration

    def _load_jwks(self) -> None:
        """Load JSON Web Key Set with caching."""
        if not self._should_refresh_jwks():
            return
            
        try:
            # Track operation
            track_auth_operation('load_jwks')
            start_time = datetime.utcnow()

            # Get JWKS
            response = requests.get(self.jwks_uri)
            response.raise_for_status()
            self.jwks = response.json()
            self.jwks_last_updated = datetime.utcnow()
            
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_auth_latency(duration)

            log_info("JWKS refreshed", {"jwks_uri": self.jwks_uri})

        except Exception as e:
            track_auth_error()
            log_error("Failed to load JWKS", {
                "error": str(e),
                "jwks_uri": self.jwks_uri
            })
            raise

    def _get_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """Get key from JWKS by key ID.
        
        Args:
            kid: Key ID to find
            
        Returns:
            Key if found, None otherwise
        """
        if not self.jwks:
            self._load_jwks()
            
        if not self.jwks:
            return None
            
        for key in self.jwks["keys"]:
            if key["kid"] == kid:
                return key
        return None

    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate Azure AD access token.
        
        Args:
            token: Token to validate
            
        Returns:
            Decoded token claims
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            # Track operation
            track_auth_operation('validate_token')
            start_time = datetime.utcnow()

            # Get unverified headers to get key ID
            headers = jwt.get_unverified_header(token)
            kid = headers.get("kid")
            
            if not kid:
                raise ValueError("Token missing key ID")
                
            # Get signing key
            key = self._get_key(kid)
            if not key:
                # Try refreshing JWKS if key not found
                self._load_jwks()
                key = self._get_key(kid)
                if not key:
                    raise ValueError("Signing key not found")
            
            # Validate token with all required checks
            decoded = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iat": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "require_exp": True,
                    "require_iat": True,
                    "require_nbf": True
                }
            )
            
            # Validate issuer
            if decoded["iss"] != f"https://login.microsoftonline.com/{self.tenant_id}/v2.0":
                raise ValueError("Invalid token issuer")
                
            # Check for required claims
            required_claims = ["sub", "oid"]
            for claim in required_claims:
                if claim not in decoded:
                    raise ValueError(f"Missing required claim: {claim}")
                    
            # Check token not used before valid time
            now = datetime.utcnow().timestamp()
            if "nbf" in decoded and decoded["nbf"] > now:
                raise ValueError("Token not yet valid")
                
            # Check token not expired
            if "exp" in decoded and decoded["exp"] < now:
                raise ValueError("Token expired")
                
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_auth_latency(duration)

            return decoded
            
        except PyJWTError as e:
            track_auth_error()
            log_error("Token validation failed", {"error": str(e)})
            raise AuthenticationError(
                f"Invalid authentication token: {str(e)}",
                details={"error": str(e)}
            )
        except Exception as e:
            track_auth_error()
            log_error("Token validation error", {"error": str(e)})
            raise AuthenticationError(
                f"Token validation failed: {str(e)}",
                details={"error": str(e)}
            )

    def get_user_info(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user info from token claims.
        
        Args:
            token_data: Token claims
            
        Returns:
            User info dictionary
            
        Raises:
            AuthenticationError: If user info extraction fails
        """
        try:
            # Track operation
            track_auth_operation('get_user_info')

            # Extract user info
            user_info = {
                "id": token_data.get("oid"),  # Object ID
                "email": token_data.get("email"),
                "name": token_data.get("name"),
                "roles": token_data.get("roles", []),
                "groups": token_data.get("groups", [])
            }
            
            # Validate required fields
            if not user_info["id"]:
                raise ValueError("Missing user ID in token")
                
            return user_info

        except Exception as e:
            track_auth_error()
            log_error("Failed to get user info", {
                "error": str(e),
                "token_data": str(token_data)
            })
            raise AuthenticationError(
                f"Failed to get user info: {str(e)}",
                details={"error": str(e)}
            )
