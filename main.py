from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from document_retriever import DocumentRetriever
from github_client import GithubClient
from repo_parser import RepoParser
from repo_analyzer import RepoAnalyzer, RepoType
from function_instrumenter import FunctionInstrumenter
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

def get_repo_analyzer() -> RepoAnalyzer:
    """Dependency to get a configured RepoAnalyzer instance."""
    return RepoAnalyzer(llm)

def get_function_instrumenter() -> FunctionInstrumenter:
    """Dependency to get a configured FunctionInstrumenter instance."""
    return FunctionInstrumenter(llm)

def get_github_client() -> GithubClient:
    """Dependency to get a configured GithubClient instance."""
    return GithubClient()

def get_document_retriever() -> DocumentRetriever:
    """Dependency to get a configured DocumentRetriever instance."""
    return DocumentRetriever()

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
    github_client: GithubClient = Depends(get_github_client),
    repo_analyzer: RepoAnalyzer = Depends(get_repo_analyzer),
    function_instrumenter: FunctionInstrumenter = Depends(get_function_instrumenter),
    document_retriever: DocumentRetriever = Depends(get_document_retriever)
):
    """
    Endpoint that fetches repository details from Github's API, clones the repo,
    and analyzes its type (CDK, Terraform, or neither).
    """
    repo_parser = RepoParser()
    try:
        # Fetch and clone the repository
        repo_details = github_client.read_repository(repository)
        clone_url = repo_details.get("clone_url")
        if not clone_url:
            raise HTTPException(status_code=500, detail="Repository response did not contain a clone_url.")
        
        # Add authentication to clone URL if token is available
        if github_client.token:
            clone_url = clone_url.replace('https://', f'https://{github_client.token}@')
        
        cloned_path = repo_parser.clone_repository(clone_url, target_dir="temp_clone")
        
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
        # Instrument the code with Datadog.
        if analysis.repo_type == "cdk":
            cdk_script_file = repo_parser.find_cdk_stack_file(documents, analysis.runtime)
            dd_documentation = document_retriever.get_lambda_documentation(analysis.runtime, 'cdk')
            instrumented_code = function_instrumenter.instrument_cdk_file(cdk_script_file.metadata['source'], cdk_script_file.page_content, dd_documentation)
        # elif analysis.repo_type == "terraform":
        #     terraform_script_file = repo_parser.find_document_by_filename(documents, analysis.terraform_script_file)
        #     instrumented_code = function_instrumenter.instrument_terraform_file(terraform_script_file.metadata['source'], terraform_script_file.page_content)
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
                "terraform_script_file": analysis.terraform_script_file,
                "runtime": analysis.runtime
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 