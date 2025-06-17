import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from github.GithubException import GithubException

from dependencies import (get_document_retriever, get_function_instrumenter,
                          get_github_client, get_pr_description_generator,
                          get_repo_analyzer)
from llm.function_instrumenter import FunctionInstrumenter
from llm.pr_description_generator import PRDescriptionGenerator
from llm.repo_analyzer import RepoAnalyzer
from util.document_retriever import DocumentRetriever
from util.github_client import GithubClient
from util.repo_parser import RepoParser

from ddtrace.llmobs.decorators import workflow
from ddtrace import llmobs

router = APIRouter()


@router.get("/instrument")
@workflow(name="instrument-repo")
async def instrument(
    repository: str,
    request: Request,
    github_client: GithubClient = Depends(get_github_client),
    repo_analyzer: RepoAnalyzer = Depends(get_repo_analyzer),
    function_instrumenter: FunctionInstrumenter = Depends(get_function_instrumenter),
    document_retriever: DocumentRetriever = Depends(get_document_retriever),
    pr_generator: PRDescriptionGenerator = Depends(get_pr_description_generator),
    additional_context: str = ""
):
    """
    Endpoint that fetches repository details from Github's API, clones the repo,
    and analyzes its type (CDK, Terraform, or neither).
    """
    start_time = datetime.now(timezone.utc).isoformat()
    repo_parser = RepoParser()
    logger = request.app.state.logger

    cloned_path = None
    try:
        # Clone the repository directly by name/URL
        with llmobs.LLMObs.task(name="clone-and-analyze-repo") as span:
            cloned_path = github_client.clone_repository(repository)
            logger.info(f"Cloned repository {repository} to {cloned_path}")

            # Read repository contents as tree structure
            tree = repo_parser.read_repository_files(cloned_path)

            # Analyze repository type
            analysis = repo_analyzer.analyze_repo(tree)
            logger.info(f"Analyzed repository: {analysis}")

            llmobs.LLMObs.annotate(span=span, tags={
                "repository": repository,
                "repo_type": analysis.repo_type,
                "runtime": analysis.runtime
            })

        # Instrument the code with Datadog.
        with llmobs.LLMObs.task(name="instrument-code") as span:
            script_file_path = os.path.join(cloned_path, analysis.script_file)
            dd_documentation = document_retriever.get_lambda_documentation(analysis.runtime, analysis.repo_type)
            instrumented_code = function_instrumenter.instrument_file(script_file_path, analysis.repo_type.upper(), dd_documentation, analysis.runtime, additional_context)

            logger.info(f"Successfully generated instrumentation!")

            llmobs.LLMObs.annotate(span=span, tags={
                "instrumentation_type": instrumented_code.instrumentation_type,
                "files_changed": len(instrumented_code.file_changes)
            })

        repo_parts = repository.split("/")
        if len(repo_parts) != 2:
            raise HTTPException(status_code=400, detail="Repository must be in format 'owner/repo'")
        repo_owner, repo_name = repo_parts

        # Generate pull request
        with llmobs.LLMObs.task(name="create-pull-request") as span:
            try:
                pr_result = github_client.generate_pull_request(
                    repo_path=cloned_path,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    instrumentation_result=instrumented_code,
                    pr_generator=pr_generator
                )
                logger.info(f"Pull request result {pr_result}")

                llmobs.LLMObs.annotate(span=span, tags={
                    "pr_url": pr_result.get("pr_url"),
                    "pr_number": pr_result.get("pr_number")
                })
            except GithubException as pr_error:
                # Handle push/PR creation errors separately
                if pr_error.status == 403:
                    logger.warning(f"Push access denied for repository {repository}")

                    # Generate OAuth URL for authentication with push permissions
                    auth_url = f"/auth/github?repository={repository}"
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "repository_push_denied",
                            "detail": f"You don't have push access to repository '{repository}'. Please authenticate with GitHub to grant write permissions.",
                            "auth_url": auth_url,
                            "message": "Push access denied. Authentication with write permissions required."
                        }
                    )
                else:
                    # Other GitHub errors during PR creation
                    logger.error(f"GitHub API error during PR creation for repository {repository}: {pr_error}")
                    raise HTTPException(status_code=500, detail=f"GitHub API error during PR creation: {pr_error}")

        # Cleanup: Remove cloned directory after successful completion
        if cloned_path:
            shutil.rmtree(cloned_path)
            logger.debug(f"Cleaned up tmp directory: {cloned_path}")

        return {
            "received_at": start_time,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "cloned_path": cloned_path,
            "analysis": {
                "type": analysis.repo_type,
                "confidence": analysis.confidence,
                "evidence": analysis.evidence,
                "script_file": analysis.script_file,
                "runtime": analysis.runtime
            },
            "pull_request": pr_result,
            "next_steps": instrumented_code.next_steps
        }
    except GithubException as e:
        # Cleanup: Remove cloned directory on GitHub error
        if cloned_path:
            try:
                shutil.rmtree(cloned_path)
                logger.debug(f"Cleaned up tmp directory after GitHub error: {cloned_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup tmp directory {cloned_path}: {cleanup_error}")

        # Handle GitHub-specific errors (404, 403, etc.)
        if e.status == 404:
            # Repository not found - could be private, need authentication
            logger.warning(f"Repository {repository} not found (404) - likely private or doesn't exist")

            # Check if OAuth is configured
            if not os.getenv("GITHUB_CLIENT_ID"):
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "repository_not_found",
                        "detail": f"Repository '{repository}' not found. It may be private or doesn't exist. GitHub OAuth is not configured for authentication.",
                        "message": "Repository not found or private. Configure GitHub OAuth to access private repositories."
                    }
                )

            # Generate OAuth URL for authentication
            auth_url = f"/auth/github?repository={repository}"
            return JSONResponse(
                status_code=403,
                content={
                    "error": "repository_access_denied",
                    "detail": f"Repository '{repository}' not found or access denied. Please authenticate with GitHub.",
                    "auth_url": auth_url,
                    "message": "Repository access denied. Authentication required."
                }
            )
        elif e.status == 403:
            # Forbidden - could be rate limit or permission issue
            logger.warning(f"Access forbidden for repository {repository} (403)")

            # Generate OAuth URL for authentication
            auth_url = f"/auth/github?repository={repository}"
            return JSONResponse(
                status_code=403,
                content={
                    "error": "repository_access_denied",
                    "detail": f"Access denied to repository '{repository}'. You may need to authenticate or lack permissions.",
                    "auth_url": auth_url,
                    "message": "Repository access denied. Authentication required."
                }
            )
        else:
            # Other GitHub errors
            logger.error(f"GitHub API error for repository {repository}: {e}")
            raise HTTPException(status_code=500, detail=f"GitHub API error: {e}")

    except Exception as e:
        # Cleanup: Remove cloned directory on error
        if cloned_path:
            try:
                shutil.rmtree(cloned_path)
                logger.info(f"Cleaned up cloned directory after error: {cloned_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup cloned directory {cloned_path}: {cleanup_error}")

        logger.error(f"General error instrumenting repository {repository}: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.get("/check-access")
async def check_access(
    repository: str,
    request: Request,
    github_client: GithubClient = Depends(get_github_client),
):
    """
    Endpoint that checks if a repository is accessible.
    """
    logger = request.app.state.logger

    try:
        # Try to get repository info to check access
        repo = github_client.github.get_repo(repository)
        
        # If we get here, repository exists and is accessible
        return {
            "accessible": True,
            "repository": {
                "name": repo.name,
                "full_name": repo.full_name,
                "private": repo.private
            }
        }
    except GithubException as e:
        # Handle GitHub-specific errors (404, 403, etc.)
        if e.status == 404:
            # Repository not found - could be private, need authentication
            logger.warning(f"Repository {repository} not found (404) - likely private or doesn't exist")

            # Check if OAuth is configured
            if not os.getenv("GITHUB_CLIENT_ID"):
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "repository_not_found",
                        "detail": f"Repository '{repository}' not found. It may be private or doesn't exist. GitHub OAuth is not configured for authentication.",
                        "message": "Repository not found or private. Configure GitHub OAuth to access private repositories."
                    }
                )

            # Generate OAuth URL for authentication
            auth_url = f"/auth/github?repository={repository}"
            return JSONResponse(
                status_code=403,
                content={
                    "error": "repository_access_denied",
                    "detail": f"Repository '{repository}' not found or access denied. Please authenticate with GitHub.",
                    "auth_url": auth_url,
                    "message": "Repository access denied. Authentication required."
                }
            )
        elif e.status == 403:
            # Forbidden - could be rate limit or permission issue
            logger.warning(f"Access forbidden for repository {repository} (403)")

            # Generate OAuth URL for authentication
            auth_url = f"/auth/github?repository={repository}"
            return JSONResponse(
                status_code=403,
                content={
                    "error": "repository_access_denied",
                    "detail": f"Access denied to repository '{repository}'. You may need to authenticate or lack permissions.",
                    "auth_url": auth_url,
                    "message": "Repository access denied. Authentication required."
                }
            )
        else:
            # Other GitHub errors
            logger.error(f"GitHub API error for repository {repository}: {e}")
            raise HTTPException(status_code=500, detail=f"GitHub API error: {e}")
