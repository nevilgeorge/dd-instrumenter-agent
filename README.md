# DD Instrumenter Agent

An AI-powered service that automatically adds Datadog monitoring to AWS Lambda functions in CDK and Terraform projects.

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**:
   ```bash
   # Required
   export OPENAI_API_KEY="your_openai_api_key"
   export DD_API_KEY="your_datadog_api_key"  # Use a key from Org 2 for LLMObs traces
   
   # Optional
   export GITHUB_TOKEN="your_github_token"  # For higher API rate limits
   export LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
   
   # Optional: GitHub OAuth for private repositories
   export GITHUB_CLIENT_ID="your_github_client_id"
   export GITHUB_CLIENT_SECRET="your_github_client_secret"
   export GITHUB_OAUTH_REDIRECT_URI="http://127.0.0.1:8000/auth/github/callback"
   ```

3. **Start the service**:
   ```bash
   python3 run.py
   ```

4. **Access the web interface**: http://127.0.0.1:8000

## What It Does

The DD Instrumenter Agent analyzes your repository and automatically:

- **Detects** CDK or Terraform infrastructure code
- **Identifies** AWS Lambda functions 
- **Adds** Datadog monitoring layers and configuration
- **Creates** a pull request with the instrumented code

### Instrumentation Includes:
- Datadog Lambda Extension layer for metrics
- Datadog Tracing layer for distributed traces
- Environment variables: `DD_ENV`, `DD_SERVICE`, `DD_VERSION`, `DD_API_KEY_SECRET_ARN`
- Required IAM permissions for Secrets Manager access

## API Endpoints

### `GET /instrument`
Analyzes and instruments a repository.

**Query Parameters:**
- `repository`: GitHub repository in format `owner/repo`
- `additional_context`: Optional instructions for instrumentation

**Response:**
```json
{
  "analysis": {
    "type": "cdk|terraform|neither",
    "confidence": 0.95,
    "evidence": ["Found cdk.json", "Found Stack class in lib/my-stack.ts"],
    "script_file": "lib/my-stack.ts",
    "runtime": "node.js"
  },
  "pull_request": {
    "pr_url": "https://github.com/owner/repo/pull/123",
    "pr_number": 123
  }
}
```

### `GET /health`
Health check endpoint.

## LLMObs Monitoring

The service includes Datadog LLMObs tracing to monitor AI operations. To view traces:

1. **Set DD_API_KEY**: Use an API key from **Org 2** 
2. **View traces**: https://app.datadoghq.com/llm/applications?query=%40ml_app%3Add-instrumenter-agent

This provides visibility into:
- Repository analysis performance
- Code instrumentation success rates
- Token usage and costs
- Error tracking

## Supported Projects

- **CDK**: TypeScript, Python, Java, Go, C#
- **Terraform**: All Lambda runtimes
- **Detection**: Automatic based on file structure and dependencies

## Development

Built with:
- **FastAPI** - Web framework
- **OpenAI GPT-4** - Code analysis and instrumentation  
- **GitHub API** - Repository access and PR creation
- **Datadog LLMObs** - AI operation monitoring

## GitHub OAuth Setup (Optional)

For private repository access:

1. Create OAuth App at GitHub Settings > Developer settings > OAuth Apps
2. Set Authorization callback URL: `http://127.0.0.1:8000/auth/github/callback`
3. Configure environment variables with OAuth credentials

## Troubleshooting

- **Port conflicts**: App auto-finds available ports (8000-8020)
- **API limits**: Set `GITHUB_TOKEN` for higher rate limits
- **Private repos**: Configure GitHub OAuth
- **Health check**: Visit `/health` endpoint