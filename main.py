from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from github_client import GithubClient
from filesystem_utils import FileSystemUtils
from repo_analyzer import RepoAnalyzer
from function_instrumenter import FunctionInstrumenter
from pr_description_generator import PRDescriptionGenerator
import os
import logging
from langchain_openai import ChatOpenAI
# Enable LangChain debug logging
logging.getLogger("langchain").setLevel(logging.DEBUG)

app = FastAPI(
    title="DD Instrumenter Agent",
    description="A FastAPI server for the DD Instrumenter Agent",
    version="1.0.0"
)

llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Initialize global instances
github_client = GithubClient()
fs_utils = FileSystemUtils()

def get_repo_analyzer() -> RepoAnalyzer:
    """Dependency to get a configured RepoAnalyzer instance."""
    return RepoAnalyzer(llm)

def get_function_instrumenter() -> FunctionInstrumenter:
    """Dependency to get a configured FunctionInstrumenter instance."""
    return FunctionInstrumenter(llm)

def get_pr_description_generator() -> PRDescriptionGenerator:
    """Dependency to get a configured PRDescriptionGenerator instance."""
    return PRDescriptionGenerator(llm)

@app.get("/")
async def index():
    """
    Root endpoint that returns a welcome message.
    """
    return {
        "message": "Welcome to DD Instrumenter Agent API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

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

@app.get("/read-repository")
async def read_repository(
    repository: str,
    repo_analyzer: RepoAnalyzer = Depends(get_repo_analyzer),
    function_instrumenter: FunctionInstrumenter = Depends(get_function_instrumenter)
):
    """
    Endpoint that fetches repository details from Github's API, clones the repo,
    and analyzes its type (CDK, Terraform, or neither).
    """
    try:
        # Fetch and clone the repository
        repo_details = github_client.read_repository(repository)
        clone_url = repo_details.get("clone_url")
        if not clone_url:
            raise HTTPException(status_code=500, detail="Repository response did not contain a clone_url.")
        cloned_path = github_client.clone_repository(clone_url, target_dir="temp_clone")

        # Read repository contents
        documents = fs_utils.load_documents_from_directory(cloned_path)
        # Analyze repository type
        analysis = repo_analyzer.analyze_repo(documents)
        # Instrument the code with Datadog.
        if analysis.repo_type == "cdk":
            cdk_script_file = fs_utils.find_document_by_filename(documents, analysis.cdk_script_file)
            instrumented_code = function_instrumenter.instrument_cdk_file(cdk_script_file.metadata['source'], cdk_script_file.page_content)
        elif analysis.repo_type == "terraform":
            terraform_script_file = fs_utils.find_document_by_filename(documents, analysis.terraform_script_file)
            instrumented_code = function_instrumenter.instrument_terraform_file(terraform_script_file.metadata['source'], terraform_script_file.page_content)
        else:
            raise HTTPException(status_code=500, detail="Repository type not supported.")

        return {
            "repository": repo_details,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "cloned_path": cloned_path,
            "analysis": {
                "type": analysis.repo_type,
                "confidence": analysis.confidence,
                "evidence": analysis.evidence,
                "cdk_script_file": analysis.cdk_script_file,
                "terraform_script_file": analysis.terraform_script_file
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@app.post("/generate-pull-request")
async def generate_pull_request(
    repository: str,
    repo_analyzer: RepoAnalyzer = Depends(get_repo_analyzer),
    function_instrumenter: FunctionInstrumenter = Depends(get_function_instrumenter),
    pr_generator: PRDescriptionGenerator = Depends(get_pr_description_generator)
):
    """
    Complete workflow: clone repo, analyze, instrument, and create PR.
    """
    try:
        # Step 1: Fetch and clone repository
        repo_details = github_client.read_repository(repository)
        clone_url = repo_details.get("clone_url")
        if not clone_url:
            raise HTTPException(status_code=500, detail="Repository response did not contain a clone_url.")

        cloned_path = github_client.clone_repository(clone_url, target_dir="temp_clone")

        # Step 2: Analyze repository type
        documents = fs_utils.load_documents_from_directory(cloned_path)
        analysis = repo_analyzer.analyze_repo(documents)

        # Step 3: Instrument the code
        if analysis.repo_type == "cdk":
            script_file = fs_utils.find_document_by_filename(documents, analysis.cdk_script_file)
            instrumentation_result = function_instrumenter.instrument_cdk_file(
                script_file.metadata['source'],
                script_file.page_content
            )
        elif analysis.repo_type == "terraform":
            script_file = fs_utils.find_document_by_filename(documents, analysis.terraform_script_file)
            instrumentation_result = function_instrumenter.instrument_terraform_file(
                script_file.metadata['source'],
                script_file.page_content
            )
        else:
            raise HTTPException(status_code=500, detail="Repository type not supported.")

        # Step 4: Extract repo owner/name for PR creation
        repo_parts = repository.split("/")
        if len(repo_parts) != 2:
            raise HTTPException(status_code=400, detail="Repository must be in format 'owner/repo'")
        repo_owner, repo_name = repo_parts

        # Step 5: Generate pull request
        pr_result = github_client.generate_pull_request(
            repo_path=cloned_path,
            repo_owner=repo_owner,
            repo_name=repo_name,
            instrumentation_result=instrumentation_result,
            pr_generator=pr_generator
        )

        return {
            "repository": repository,
            "analysis": {
                "type": analysis.repo_type,
                "confidence": analysis.confidence,
                "evidence": analysis.evidence
            },
            "instrumentation": {
                "type": instrumentation_result.instrumentation_type,
                "files_changed": list(instrumentation_result.file_changes.keys())
            },
            "pull_request": pr_result,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
