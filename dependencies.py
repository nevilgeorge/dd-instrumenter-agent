from fastapi import HTTPException, Request

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


def get_github_client() -> GithubClient:
    """Dependency to get a configured GithubClient instance."""
    return GithubClient()


def get_document_retriever() -> DocumentRetriever:
    """Dependency to get a configured DocumentRetriever instance."""
    return DocumentRetriever()
