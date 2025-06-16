import json
import logging
import sys
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone

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

def get_github_client() -> GithubClient:
    """Dependency to get a configured GithubClient instance."""
    return GithubClient()

def get_document_retriever() -> DocumentRetriever:
    """Dependency to get a configured DocumentRetriever instance."""
    return DocumentRetriever()

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

@app.get("/instrument")
async def instrument(
    repository: str,
    github_client: GithubClient = Depends(get_github_client),
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
        # Clone the repository directly by name/URL
        cloned_path = github_client.clone_repository(repository, target_dir="temp_clone")

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
