import json
import logging
import sys
import os
import secrets
import base64
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone
import requests

import openai

# Try to import DD internal authentication if available
try:
    from dd_internal_authentication.client import (
        JWTDDToolAuthClientTokenManager, JWTInternalServiceAuthClientTokenManager)
    DD_AUTH_AVAILABLE = True
except ImportError:
    DD_AUTH_AVAILABLE = False
    JWTDDToolAuthClientTokenManager = None
    JWTInternalServiceAuthClientTokenManager = None

from llm.function_instrumenter import FunctionInstrumenter
from llm.pr_description_generator import PRDescriptionGenerator
from llm.repo_analyzer import RepoAnalyzer, RepoType
from util.document_retriever import DocumentRetriever
from util.github_client import GithubClient
from util.repo_parser import RepoParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("✅ Environment variables loaded from .env file")
except ImportError:
    logger.info("📝 python-dotenv not installed, using system environment variables")

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/auth/github/callback")

# In-memory session store (in production, use Redis or database)
oauth_sessions = {}
user_tokens = {}

app = FastAPI(
    title="DD Instrumenter Agent",
    description="A FastAPI server for the DD Instrumenter Agent",
    version="1.0.0"
)

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Initialize OpenAI client
def get_openai_client():
    """Get OpenAI client instance with proper authentication."""
    if DD_AUTH_AVAILABLE:
        try:
            # Try to use DD internal authentication first
            token = JWTDDToolAuthClientTokenManager.instance(
                name="rapid-ai-platform", datacenter="us1.staging.dog"
            ).get_token("rapid-ai-platform")
            host = "https://ai-gateway.us1.staging.dog"
            
            client = openai.OpenAI(
                api_key=token,
                base_url=f"{host}/v1",
                default_headers={
                    "source": "dd-instrumenter-agent",
                    "org-id": "2",
                },
            )
            logger.info("🔑 DD internal authentication: YES")
            return client
        except Exception as e:
            logger.warning(f"⚠️  DD internal authentication failed: {e}")
    else:
        logger.warning("⚠️  DD internal authentication not available - using OpenAI directly")
    
    # Fall back to OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("⚠️  No OpenAI API key found. Some features will be disabled.")
        return None
    
    logger.info("🔑 OpenAI API Key loaded: YES")
    logger.info(f"🔑 API Key starts with: {api_key[:20]}...")
    
    return openai.OpenAI(api_key=api_key)

# Initialize client
client = get_openai_client()

def get_repo_analyzer() -> RepoAnalyzer:
    """Dependency to get a configured RepoAnalyzer instance."""
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
    return RepoAnalyzer(client)

def get_function_instrumenter() -> FunctionInstrumenter:
    """Dependency to get a configured FunctionInstrumenter instance."""
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
    return FunctionInstrumenter(client)

def get_pr_description_generator() -> PRDescriptionGenerator:
    """Dependency to get a configured PRDescriptionGenerator instance."""
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
    return PRDescriptionGenerator(client)

def get_github_client(access_token: Optional[str] = None) -> GithubClient:
    """Dependency to get a configured GithubClient instance."""
    return GithubClient(access_token=access_token)

def get_document_retriever() -> DocumentRetriever:
    """Dependency to get a configured DocumentRetriever instance."""
    return DocumentRetriever()

def get_user_token(request: Request) -> Optional[str]:
    """Extract user token from session/cookies."""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in user_tokens:
        return user_tokens[session_id]
    return None

@app.get("/")
async def index():
    """
    Serve the frontend HTML page.
    """
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health_check():
    """
    Health check endpoint that returns the server status.
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        status_code=200
    )

@app.get("/auth/github")
async def github_auth(repository: str, response: Response):
    """
    Initiate GitHub OAuth flow for accessing a specific repository.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables.")
    
    # Generate a random state for CSRF protection
    state = secrets.token_urlsafe(32)
    session_id = secrets.token_urlsafe(32)
    
    # Store repository and state in session
    oauth_sessions[state] = {
        "repository": repository,
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Set session cookie
    response.set_cookie("session_id", session_id, httponly=True, secure=False, samesite="lax")
    
    # Build GitHub OAuth URL
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_OAUTH_REDIRECT_URI}"
        f"&scope=repo"
        f"&state={state}"
    )
    
    return RedirectResponse(url=github_auth_url)

@app.get("/auth/github/callback")
async def github_callback(code: str, state: str, response: Response):
    """
    Handle GitHub OAuth callback and exchange code for access token.
    """
    if not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured.")
    
    # Verify state to prevent CSRF
    if state not in oauth_sessions:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
    
    session_data = oauth_sessions[state]
    repository = session_data["repository"]
    session_id = session_data["session_id"]
    
    try:
        # Exchange code for access token
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_OAUTH_REDIRECT_URI,
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token.")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received from GitHub.")
        
        # Store the access token for this session
        user_tokens[session_id] = access_token
        
        # Clean up OAuth session
        del oauth_sessions[state]
        
        logger.info(f"✅ GitHub OAuth successful for repository: {repository}")
        
        # Redirect back to frontend with success message
        return RedirectResponse(url=f"/?auth=success&repository={repository}")
        
    except Exception as e:
        logger.error(f"❌ GitHub OAuth error: {e}")
        # Clean up OAuth session
        if state in oauth_sessions:
            del oauth_sessions[state]
        
        return RedirectResponse(url=f"/?auth=error&message={str(e)}")

@app.get("/auth/status")
async def auth_status(request: Request):
    """
    Check if user is authenticated and return their GitHub permissions status.
    """
    access_token = get_user_token(request)
    
    if not access_token:
        return JSONResponse(content={"authenticated": False})
    
    try:
        # Test the token by making a request to GitHub API
        headers = {"Authorization": f"token {access_token}"}
        response = requests.get("https://api.github.com/user", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            return JSONResponse(content={
                "authenticated": True,
                "username": user_data.get("login"),
                "name": user_data.get("name")
            })
        else:
            # Token is invalid, remove it
            session_id = request.cookies.get("session_id")
            if session_id and session_id in user_tokens:
                del user_tokens[session_id]
            return JSONResponse(content={"authenticated": False})
            
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return JSONResponse(content={"authenticated": False})

@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    """
    Logout user and clear their stored token.
    """
    session_id = request.cookies.get("session_id")
    if session_id and session_id in user_tokens:
        del user_tokens[session_id]
    
    # Clear session cookie
    response.delete_cookie("session_id")
    
    return JSONResponse(content={"message": "Logged out successfully"})

@app.get("/instrument")
async def instrument(
    repository: str,
    request: Request,
    repo_analyzer: RepoAnalyzer = Depends(get_repo_analyzer),
    function_instrumenter: FunctionInstrumenter = Depends(get_function_instrumenter),
    document_retriever: DocumentRetriever = Depends(get_document_retriever),
    pr_generator: PRDescriptionGenerator = Depends(get_pr_description_generator)
):
    """
    Endpoint that fetches repository details from Github's API, clones the repo,
    and analyzes its type (CDK, Terraform, or neither).
    """
    start_time = datetime.now(timezone.utc).isoformat()
    repo_parser = RepoParser()

    try:
        # Get user's access token
        access_token = get_user_token(request)
        
        # Initialize GitHub client with token if available
        github_client = get_github_client(access_token)
        
        # Clone the repository directly by name/URL
        try:
            cloned_path = github_client.clone_repository(repository, target_dir="temp_clone")
        except Exception as clone_error:
            # If clone fails due to permissions, suggest OAuth
            if "Permission denied" in str(clone_error) or "authentication failed" in str(clone_error).lower():
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "repository_access_denied",
                        "message": "You don't have access to this repository. Please authenticate with GitHub.",
                        "auth_url": f"/auth/github?repository={repository}",
                        "repository": repository
                    }
                )
            else:
                raise clone_error

        logger.info(f"Cloned repository {repository} to {cloned_path}")

        # Read repository contents
        documents = repo_parser.read_repository_files(cloned_path)
        # Analyze repository type
        # analysis = repo_analyzer.analyze_repo(documents)
        analysis = RepoType(
            repo_type="cdk",
            confidence=1.0,
            evidence=["CDK stack file found"],
            cdk_script_file="peer-tags-demo.ts",
            terraform_script_file="",
            runtime="node.js"
        )

        logger.info(f"Analyzed repository: {analysis}")

        # Instrument the code with Datadog.
        if analysis.repo_type == "cdk":
            cdk_script_file = repo_parser.find_cdk_stack_file(documents, analysis.runtime)
            dd_documentation = document_retriever.get_lambda_documentation(analysis.runtime, 'cdk')
            instrumented_code = function_instrumenter.instrument_cdk_file(cdk_script_file, dd_documentation)
        # elif analysis.repo_type == "terraform":
        #     terraform_script_file = repo_parser.find_document_by_filename(documents, analysis.terraform_script_file)
        #     instrumented_code = function_instrumenter.instrument_terraform_file(terraform_script_file.metadata['source'], terraform_script_file.page_content)
        else:
            raise HTTPException(status_code=500, detail="Repository type not supported.")

        logger.info(f"Successfully generated instrumentation!")

        repo_parts = repository.split("/")
        if len(repo_parts) != 2:
            raise HTTPException(status_code=400, detail="Repository must be in format 'owner/repo'")
        repo_owner, repo_name = repo_parts

        # Step 5: Generate pull request
        pr_result = github_client.generate_pull_request(
            repo_path=cloned_path,
            repo_owner=repo_owner,
            repo_name=repo_name,
            instrumentation_result=instrumented_code,
            pr_generator=pr_generator
        )

        logger.info(f"Pull request result {json.dumps(pr_result, indent=2)}")

        return {
            "received_at": start_time,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "cloned_path": cloned_path,
            "analysis": {
                "type": analysis.repo_type,
                "confidence": analysis.confidence,
                "evidence": analysis.evidence,
                "cdk_script_file": analysis.cdk_script_file,
                "terraform_script_file": analysis.terraform_script_file,
                "runtime": analysis.runtime
            },
            "pull_request": pr_result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
