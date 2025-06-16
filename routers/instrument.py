from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from dependencies import (get_document_retriever, get_function_instrumenter,
                          get_github_client, get_pr_description_generator,
                          get_repo_analyzer)
from llm.function_instrumenter import FunctionInstrumenter
from llm.pr_description_generator import PRDescriptionGenerator
from llm.repo_analyzer import RepoAnalyzer, RepoType
from util.document_retriever import DocumentRetriever
from util.github_client import GithubClient
from util.repo_parser import RepoParser

router = APIRouter()


@router.get("/instrument")
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

    try:
        # Clone the repository directly by name/URL
        cloned_path = github_client.clone_repository(repository, target_dir="temp_clone")

        logger.info(f"Cloned repository {repository} to {cloned_path}")

        # Read repository contents
        documents = repo_parser.read_repository_files(cloned_path)

        # Analyze repository type
        analysis = repo_analyzer.analyze_repo(documents)

        logger.info(f"Analyzed repository: {analysis}")

        # Instrument the code with Datadog.
        if analysis.repo_type == "cdk":
            cdk_script_file = repo_parser.find_cdk_stack_file(documents, analysis.runtime)
            dd_documentation = document_retriever.get_lambda_documentation(analysis.runtime, 'cdk')
            instrumented_code = function_instrumenter.instrument_cdk_file(cdk_script_file, dd_documentation, additional_context)
        elif analysis.repo_type == "terraform":
            terraform_script_file = repo_parser.find_terraform_file(documents, analysis.runtime)
            dd_documentation = document_retriever.get_lambda_documentation(analysis.runtime, 'terraform')
            instrumented_code = function_instrumenter.instrument_terraform_file(
                terraform_script_file.metadata['source'],
                terraform_script_file.page_content,
                dd_documentation,
                additional_context
            )
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

        logger.info(f"Pull request result {pr_result}")

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
