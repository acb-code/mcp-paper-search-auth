import os
from pathlib import Path
import json

import httpx
from dotenv import load_dotenv
from pypdf import PdfReader
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.provider import TokenVerifier, AccessToken
from pydantic import AnyHttpUrl
from jose import jwt, JWTError

load_dotenv()

# --- Config ---
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")
PDF_DIR = Path(os.getenv("PDF_DIR", "/data/pdfs"))

# --- Auth0 Token Verifier ---
class Auth0TokenVerifier(TokenVerifier):
    def __init__(self):
        self._jwks: dict | None = None

    def _get_jwks(self) -> dict:
        if not self._jwks:
            resp = httpx.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
            resp.raise_for_status()
            self._jwks = resp.json()
        return self._jwks

    async def verify_token(self, token: str) -> AccessToken:
        try:
            header = jwt.get_unverified_header(token)
            print(f"DEBUG token header: {header}")
            jwks = self._get_jwks()
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            # If kid present, match it; otherwise try all keys
            keys = (
                [k for k in jwks["keys"] if k["kid"] == kid]
                if kid
                else jwks["keys"]
            )

            if not keys:
                raise ValueError("No matching public key found")

            last_error = None
            for key in keys:
                try:
                    payload = jwt.decode(
                        token,
                        key,
                        algorithms=["RS256"],
                        # audience=AUTH0_AUDIENCE,
                        options={"verify_aud": False},  # skip audience check
                        issuer=f"https://{AUTH0_DOMAIN}/",
                    )
                    return AccessToken(
                        token=token,
                        client_id=payload.get("azp", payload.get("sub", "")),
                        scopes=payload.get("scope", "openid").split(),
                        expires_at=payload.get("exp"),
                    )
                except JWTError as e:
                    last_error = e
                    continue

            raise ValueError(f"Token verification failed with all keys: {last_error}")

        except (ValueError, httpx.HTTPError) as e:
            raise ValueError(f"Token verification failed: {e}")


# --- MCP Server ---
mcp = FastMCP(
    "pdf-search",
    host="0.0.0.0",
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(f"https://{AUTH0_DOMAIN}/"),
        resource_server_url=AnyHttpUrl(SERVER_URL),
        required_scopes=["openid"],
    ),
    token_verifier=Auth0TokenVerifier(),
)


# --- Tools ---

@mcp.tool()
def search_pdfs(query: str) -> str:
    """
    Search through all PDFs in the configured directory for the given query string.
    Returns matching excerpts with source filenames.

    Args:
        query: Text to search for (case-insensitive)
    """
    if not PDF_DIR.exists():
        return json.dumps({"error": f"PDF directory not found: {PDF_DIR}"})

    results = []
    query_lower = query.lower()

    for pdf_path in PDF_DIR.glob("**/*.pdf"):
        try:
            reader = PdfReader(pdf_path)
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if query_lower in text.lower():
                    idx = text.lower().find(query_lower)
                    start = max(0, idx - 150)
                    end = min(len(text), idx + 150)
                    excerpt = text[start:end].strip().replace("\n", " ")
                    results.append({
                        "file": pdf_path.name,
                        "page": page_num,
                        "excerpt": f"...{excerpt}...",
                    })
        except Exception as e:
            results.append({"file": pdf_path.name, "error": str(e)})

    if not results:
        return json.dumps({"message": f"No results found for '{query}'"})

    return json.dumps({"query": query, "results": results}, indent=2)


@mcp.tool()
def list_pdfs() -> str:
    """List all PDF files available in the search directory."""
    if not PDF_DIR.exists():
        return json.dumps({"error": f"PDF directory not found: {PDF_DIR}"})

    files = [
        {"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1)}
        for p in sorted(PDF_DIR.glob("**/*.pdf"))
    ]
    return json.dumps({"count": len(files), "files": files}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")