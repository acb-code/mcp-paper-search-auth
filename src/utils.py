import urllib.request
import json
from jose import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

# Inherit from the official TokenVerifier class
class Auth0TokenVerifier(TokenVerifier):
    def __init__(self, domain: str, audience: str):
        self.issuer = f"https://{domain}/"
        self.audience = audience
        jwks_url = f"{self.issuer}.well-known/jwks.json"
        
        try:
            with urllib.request.urlopen(jwks_url) as response:
                self.jwks = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Failed to fetch JWKS from {jwks_url}: {e}")
            self.jwks = {"keys": []}

    # Return the specific AccessToken object the SDK expects
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            unverified_header = jwt.get_unverified_header(token)
            rsa_key = {}
            
            for key in self.jwks.get("keys", []):
                if key["kid"] == unverified_header.get("kid"):
                    rsa_key = key
                    break
            
            if not rsa_key:
                print("Token rejected: Unable to find appropriate key in JWKS.")
                return None
            
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer
            )
            
            # Auth0 scopes are space-separated strings, MCP expects a list
            scope_str = payload.get("scope", "")
            scopes = scope_str.split(" ") if scope_str else []
            
            # Return the official Pydantic model
            return AccessToken(
                token=token,
                client_id=payload.get("sub", "unknown"),
                scopes=scopes,
                expires_at=payload.get("exp"), 
                resource=self.audience
            )
            
        except Exception as e:
            print(f"Token verification failed: {e}")
            return None

def create_auth0_verifier(domain: str, audience: str):
    return Auth0TokenVerifier(domain, audience)