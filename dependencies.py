from fastapi import HTTPException, Request
from typing import Optional

from llm.function_instrumenter import FunctionInstrumenter
from llm.pr_description_generator import PRDescriptionGenerator
from llm.repo_analyzer import RepoAnalyzer
from util.document_retriever import DocumentRetriever
from util.github_client import GithubClient


def get_repo_analyzer(request: Request) -> RepoAnalyzer:
    """Dependency to get a configured RepoAnalyzer instance."""
    if not request.app.state.openai_client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    return RepoAnalyzer(request.app.state.openai_client)


def get_function_instrumenter(request: Request) -> FunctionInstrumenter:
    """Dependency to get a configured FunctionInstrumenter instance."""
    if not request.app.state.openai_client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    return FunctionInstrumenter(request.app.state.openai_client)


def get_pr_description_generator(request: Request) -> PRDescriptionGenerator:
    """Dependency to get a configured PRDescriptionGenerator instance."""
    if not request.app.state.openai_client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    return PRDescriptionGenerator(request.app.state.openai_client)


def get_user_token(request: Request) -> Optional[str]:
    """Extract user's OAuth access token from session/cookies."""
    # Access the user_tokens from app state (we'll need to move this there)
    session_id = request.cookies.get("session_id")
    if session_id and hasattr(request.app.state, 'user_tokens'):
        return request.app.state.user_tokens.get(session_id)
    return None


def get_github_client(request: Request) -> GithubClient:
    """Dependency to get a configured GithubClient instance with user's OAuth token if available."""
    access_token = get_user_token(request)
    return GithubClient(access_token=access_token)


def get_document_retriever() -> DocumentRetriever:
    """Dependency to get a configured DocumentRetriever instance."""
    return DocumentRetriever()
