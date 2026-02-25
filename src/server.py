import os
import json
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from jose import jwt, JWTError
from pypdf import PdfReader
from mcp.server.fastmcp import FastMCP

load_dotenv()

# --- Config ---
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
PDF_DIR = Path(os.getenv("PDF_DIR", "data/pdfs"))

# --- Auth0 token verification ---
def get_auth0_public_key(token: str) -> dict:
    """Fetch JWKS and find the key matching the token's kid."""
    header = jwt.get_unverified_header(token)
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    resp = httpx.get(jwks_url)
    resp.raise_for_status()
    jwks = resp.json()
    for key in jwks["keys"]:
        if key["kid"] == header["kid"]:
            return key
    raise ValueError("No matching public key found")

def verify_token(token: str) -> dict:
    """Verify Auth0 JWT and return claims."""
    public_key = get_auth0_public_key(token)
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=AUTH0_AUDIENCE,
        issuer=f"https://{AUTH0_DOMAIN}/",
    )
    return payload

# --- MCP Server ---
mcp = FastMCP("mcp-paper-search-auth")

@mcp.tool()
def search_pdfs(query: str, auth_token: str) -> str:
    """
    Search through all PDFs in the cofigured directory for the given query string.
    Returns matching excerpts with source filenames.
    
    Args:
        query: Text to search for (case-insensitive)
        auth_token: Bearer token from Auth0
    """
    # Verify auth
    try:
        claims = verify_token(auth_token)
    except (JWTError, ValueError, httpx.HTTPError) as e:
        return json.dumps({"error": f"Unauthorized: {str(e)}"})
    
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
                    # grab a small excerpt around the match
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
def list_pdfs(auth_token: str) -> str:
    """
    List all PDF files available in the search directory.
    
    Args:
        auth_token: Bearer token from Auth0
    """
    try:
        verify_token(auth_token)
    except (JWTError, ValueError, httpx.HTTPError) as e:
        return json.dumps({"error": f"Unauthorized: {str(e)}"})

    if not PDF_DIR.exists():
        return json.dumps({"error": f"PDF directory not found: {PDF_DIR}"})

    files = [
        {"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1)}
        for p in sorted(PDF_DIR.glob("**/*.pdf"))
    ]
    return json.dumps({"count": len(files), "files": files}, indent=2)


if __name__ == "__main__":
    # SSE transport for HTTP-based deployment (ngrok/Railway)
    mcp.run(transport="sse")
