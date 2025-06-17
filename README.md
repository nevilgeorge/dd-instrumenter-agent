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

```bash
export GITHUB_TOKEN="your_github_token"
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
- `GITHUB_TOKEN`: Github Token allows circumventing Github API rate limits
- `LOG_LEVEL`: Set logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL) - defaults to INFO

## Security

- GitHub token and OpenAI API key are required as environment variables

## Running the Web UI

The DD Instrumenter Agent includes a professional DataDog-style web interface for easy Lambda instrumentation.

### Quick Start

1. **Install dependencies** (if not already done):

   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables** (required):

   ```bash
   # Required: OpenAI API key for AI analysis and instrumentation
   export OPENAI_API_KEY="your_openai_api_key"

   # Optional: Set logging level (default: INFO)
   export LOG_LEVEL="DEBUG"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

   # Optional: GitHub OAuth (for private repositories)
   export GITHUB_CLIENT_ID="your_github_client_id"
   export GITHUB_CLIENT_SECRET="your_github_client_secret"
   export GITHUB_OAUTH_REDIRECT_URI="http://127.0.0.1:8000/auth/github/callback"
   ```

3. **Start the application**:

   ```bash
   python3 run.py
   ```

   Or alternatively:

   ```bash
   python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Access the web interface**:
   - Open your browser and navigate to: **http://127.0.0.1:8000**
   - The app will automatically find an available port if 8000 is in use

### Web Interface Features

- **🎯 Step-by-Step Workflow**: Guided 3-step process for Lambda instrumentation
- **🔐 GitHub OAuth Integration**: Seamless authentication for private repositories
- **📱 Responsive Design**: Works on desktop and mobile devices
- **🏢 DataDog-Style UI**: Professional interface matching DataDog's Fleet Automation
- **⚡ Real-Time Status**: Live updates on repository analysis and instrumentation progress
- **🔗 Direct PR Links**: Instant access to generated pull requests

### Usage Flow

1. **Step 1 - Repository URL**: Enter your GitHub repository URL (e.g., `username/repository-name`)
2. **Step 2 - Authentication**: Automatic GitHub OAuth if accessing private repositories
3. **Step 3 - Instrumentation**: Click "Instrument Repository" to generate DataDog instrumentation

### GitHub OAuth Setup (Optional)

For private repository access, set up a GitHub OAuth App:

1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Create a new OAuth App with:
   - **Authorization callback URL**: `http://127.0.0.1:8000/auth/github/callback`
3. Set the environment variables with your OAuth credentials

### Troubleshooting

- **Port conflicts**: The app automatically finds available ports (8000-8020)
- **Missing API key**: Ensure `OPENAI_API_KEY` is set in your environment
- **Private repos**: Set up GitHub OAuth credentials for private repository access
- **Health check**: Visit `http://127.0.0.1:8000/health` to verify the service is running
