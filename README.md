# DD Instrumenter Agent

A FastAPI-based server for the DD Instrumenter Agent.

## Setup

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export OPENAI_API_KEY="your_openai_api_key"
```

## API Endpoints

### GET /health
Health check endpoint that returns service status.

### GET /read-repository
Analyzes a GitHub repository to determine its infrastructure type and instruments Lambda functions with Datadog.

Query Parameters:
- `repository`: URL of the GitHub repository to analyze (e.g., "https://github.com/username/repo-name")

Response (JSON):
```json
{
    "repository": {
        "name": "repo-name",
        "clone_url": "https://github.com/username/repo-name.git",
        ...
    },
    "received_at": "2024-03-14T12:00:00Z",
    "cloned_path": "/path/to/cloned/repo",
    "analysis": {
        "type": "cdk|terraform|neither",
        "confidence": 0.95,
        "evidence": ["Found cdk.json", "Found aws-cdk-lib dependency"],
        "cdk_script_file": "path/to/cdk/app.py",
        "terraform_script_file": "path/to/main.tf"
    }
}
```

If the repository contains AWS Lambda functions, they will be automatically instrumented with:
- Datadog Lambda Extension layer
- Datadog Tracing layer
- Required Datadog environment variables (DD_ENV, DD_SERVICE, DD_VERSION)

## Running the Service

Start the service with:
```bash
uvicorn main:app --reload
```

The service will be available at `http://localhost:8000`

## Development

The service uses:
- FastAPI for the web framework
- LangChain for AI analysis
- OpenAI GPT-3.5 for repository analysis and code instrumentation
- GitHub API for repository access
- Datadog for Lambda function instrumentation

## Environment Variables

- `OPENAI_API_KEY`: OpenAI API key for AI analysis and instrumentation

## Security

- GitHub token and OpenAI API key are required as environment variables