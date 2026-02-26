import os
from dotenv import load_dotenv
# 1. Use the OFFICIAL imports instead of the community package
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl 

# Make sure your utils.py contains the JWT verifier from the video
from utils import create_auth0_verifier 

load_dotenv()

AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE")
SERVER_URL = os.environ.get("SERVER_URL")
PDF_DIR = os.environ.get("PDF_DIR", "/data/pdfs")

# Ensure FastMCP endpoints match Auth0 expectations
if SERVER_URL and not SERVER_URL.endswith("/mcp"):
    SERVER_URL += "/mcp"

# Initialize the Auth Verifier
token_verifier = create_auth0_verifier(AUTH0_DOMAIN, AUTH0_AUDIENCE)

# Configure FastMCP with AuthSettings
mcp = FastMCP(
    "Local Paper Search",
    host="0.0.0.0", 
    port=8000,
    # 2. Use the correct property names for the official SDK
    token_verifier=token_verifier,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(f"https://{AUTH0_DOMAIN}/"),
        resource_server_url=AnyHttpUrl(SERVER_URL),
        # Auth0 may require you to define this scope in the Auth0 API settings
        required_scopes=["read:papers"] 
    )
)

# 5. Define the Tool
@mcp.tool()
def search_papers(query: str) -> str:
    """Searches the local PDF directory for filenames matching the query."""
    if not os.path.exists(PDF_DIR):
         return f"Error: Directory {PDF_DIR} does not exist."

    results = []
    for root, dirs, files in os.walk(PDF_DIR):
        for file in files:
            if file.endswith(".pdf") and query.lower() in file.lower():
                results.append(file)
                
    if not results:
        return f"No papers found matching '{query}'."
    
    return "Found the following papers:\n" + "\n".join(results)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")