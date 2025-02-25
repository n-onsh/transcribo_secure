import jwt
from typing import Dict, Optional
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
import os
from jwt import PyJWTError
import requests
from fastapi import HTTPException

logger = logs.get_logger(__name__)

class TokenValidator:
    def __init__(self):
        """Initialize token validator"""
        # Get Azure AD configuration
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        
        if not all([self.tenant_id, self.client_id]):
            raise ValueError("Missing required Azure AD configuration")
        
        # OpenID configuration URL
        self.config_url = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0/.well-known/openid-configuration"
        
        # Cache for JWKS
        self.jwks = None
        self.jwks_uri = None
        
        # Initialize
        self._load_openid_config()
        logger.emit(
            "Token validator initialized",
            severity=Severity.INFO,
            attributes={
                "tenant_id": self.tenant_id,
                "config_url": self.config_url
            }
        )

    def _load_openid_config(self):
        """Load OpenID configuration"""
        try:
            response = requests.get(self.config_url)
            response.raise_for_status()
            config = response.json()
            
            # Get JWKS URI
            self.jwks_uri = config["jwks_uri"]
            
            # Load JWKS
            self._load_jwks()
            
        except Exception as e:
            logger.emit(
                "Failed to load OpenID config",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "config_url": self.config_url
                }
            )
            raise ValueError(
                "Failed to load Azure AD configuration. Check:\n"
                "1. Network connectivity\n"
                "2. Azure AD tenant configuration\n"
                f"Original error: {str(e)}"
            )

    def _load_jwks(self):
        """Load JSON Web Key Set"""
        try:
            response = requests.get(self.jwks_uri)
            response.raise_for_status()
            self.jwks = response.json()
        except Exception as e:
            logger.emit(
                "Failed to load JWKS",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "jwks_uri": self.jwks_uri
                }
            )
            raise

    def _get_key(self, kid: str) -> Optional[Dict]:
        """Get key from JWKS by key ID"""
        if not self.jwks:
            self._load_jwks()
            
        for key in self.jwks["keys"]:
            if key["kid"] == kid:
                return key
        return None

    def validate_token(self, token: str) -> Dict:
        """Validate Azure AD access token"""
        try:
            # Get unverified headers to get key ID
            headers = jwt.get_unverified_header(token)
            kid = headers["kid"]
            
            # Get signing key
            key = self._get_key(kid)
            if not key:
                raise ValueError("Signing key not found")
            
            # Validate token
            decoded = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.client_id
            )
            
            # Validate claims
            if decoded["iss"] != f"https://login.microsoftonline.com/{self.tenant_id}/v2.0":
                raise ValueError("Invalid token issuer")
                
            return decoded
            
        except PyJWTError as e:
            logger.emit(
                "Token validation failed",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )
        except Exception as e:
            logger.emit(
                "Token validation error",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise HTTPException(
                status_code=500,
                detail="Token validation failed"
            )

    def get_user_info(self, token_data: Dict) -> Dict:
        """Extract user info from token claims"""
        try:
            return {
                "id": token_data.get("oid"),  # Object ID
                "email": token_data.get("email"),
                "name": token_data.get("name"),
                "roles": token_data.get("roles", []),
                "groups": token_data.get("groups", [])
            }
        except Exception as e:
            logger.emit(
                "Failed to get user info",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "token_data": str(token_data)
                }
            )
            raise
