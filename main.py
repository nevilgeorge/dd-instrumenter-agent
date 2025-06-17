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

from config import setup_logging, setup_openai_client
from routers import health, instrument


def create_app():
    """Create and configure FastAPI application."""
    logger = setup_logging()
    client = setup_openai_client()

    app = FastAPI(
        title="DD Instrumenter Agent",
        description="A FastAPI server for the DD Instrumenter Agent",
        version="1.0.0"
    )

    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

    # Store dependencies in app state
    app.state.openai_client = client
    app.state.logger = logger

    # GitHub OAuth configuration
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/auth/github/callback")

    # In-memory session store (in production, use Redis or database)
    oauth_sessions = {}
    user_tokens = {}
    
    # Store user tokens in app state so dependencies can access them
    app.state.user_tokens = user_tokens

    def get_user_token(request: Request) -> Optional[str]:
        """Extract user token from session/cookies."""
        session_id = request.cookies.get("session_id")
        logger.info(f"🔍 Session ID from cookie: {'YES' if session_id else 'NO'}")
        if session_id:
            logger.info(f"🔍 Session ID: {session_id[:10]}...")
            logger.info(f"🔍 Token exists for session: {'YES' if session_id in user_tokens else 'NO'}")
            if session_id in user_tokens:
                token = user_tokens[session_id]
                logger.info(f"🔍 Retrieved token starts with: {token[:10]}...")
                return token
        return None

    @app.get("/")
    async def index():
        """Serve the frontend HTML page."""
        return FileResponse("frontend/index.html")

    @app.get("/auth/github")
    async def github_auth(repository: str, response: Response):
        """Initiate GitHub OAuth flow for accessing a specific repository."""
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
        """Handle GitHub OAuth callback and exchange code for access token."""
        try:
            # Verify state parameter
            if state not in oauth_sessions:
                raise HTTPException(status_code=400, detail="Invalid state parameter")
            
            session_data = oauth_sessions[state]
            session_id = session_data["session_id"]
            
            # Exchange code for access token
            token_url = "https://github.com/login/oauth/access_token"
            token_data = {
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "state": state
            }
            
            token_response = requests.post(
                token_url,
                data=token_data,
                headers={"Accept": "application/json"}
            )
            
            if token_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange code for token")
            
            token_info = token_response.json()
            access_token = token_info.get("access_token")
            
            if not access_token:
                raise HTTPException(status_code=400, detail="No access token received")
            
            # Store the access token
            user_tokens[session_id] = access_token
            logger.info(f"🔍 Stored token for session: {session_id[:10]}...")
            
            # Clean up OAuth session
            del oauth_sessions[state]
            
            # Create redirect response
            redirect_response = RedirectResponse(url="/?auth=success")
            
            # Set the session cookie on the redirect response
            redirect_response.set_cookie(
                key="session_id",
                value=session_id, 
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax",
                max_age=3600,  # 1 hour
                path="/"  # Ensure cookie is available for all paths
            )
            logger.info(f"🔍 Setting session cookie: {session_id[:10]}... on redirect response")
            
            return redirect_response
            
        except Exception as e:
            logger.error(f"❌ GitHub OAuth error: {e}")
            # Clean up OAuth session
            if state in oauth_sessions:
                del oauth_sessions[state]
            
            return RedirectResponse(url=f"/?auth=error&message={str(e)}")

    @app.get("/auth/status")
    async def auth_status(request: Request):
        """Check if user is authenticated and return their GitHub permissions status."""
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
        """Logout user and clear their stored token."""
        session_id = request.cookies.get("session_id")
        if session_id and session_id in user_tokens:
            del user_tokens[session_id]
        
        # Clear session cookie
        response.delete_cookie("session_id")
        
        return JSONResponse(content={"message": "Logged out successfully"})

    # Include routers
    app.include_router(health.router)
    app.include_router(instrument.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
