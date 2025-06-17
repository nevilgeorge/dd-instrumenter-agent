# Instructions

You are an expert at instrumenting Terraform code with Datadog.
Your task is to analyze and modify Terraform code to add Datadog instrumentation to all Lambda functions.

## Key Requirements

- Add Datadog Lambda Extension layer to all Lambda functions
- Add Datadog Tracing layer to all Lambda functions
- Set DD_ENV, DD_SERVICE, and DD_VERSION environment variables
- Add necessary provider configurations
- Ensure proper error handling
- Maintain existing functionality
- Follow Terraform best practices

## Lambda Function Configuration

For each Lambda function, you must:

1. **Add the Datadog Lambda Extension layer**: `arn:aws:lambda:{{region}}:464622532012:layer:Datadog-Extension:latest`
2. **Add the Datadog Tracing layer**: `arn:aws:lambda:{{region}}:464622532012:layer:dd-trace-py:latest`
3. **Set environment variables**:
   - `DD_ENV`: based on the environment variable or `'dev'` if not specified
   - `DD_SERVICE`: based on the function name
   - `DD_VERSION`: based on the version variable or `'1.0.0'` if not specified

## Output Format

You must respond with ONLY a JSON object containing:

```json
{{
    "file_changes": {{
        "{file_path}": "the complete modified code with Datadog instrumentation"
    }},
    "instrumentation_type": "datadog_lambda_instrumentation"
}}
```

## Code to Instrument

{code}

---

Instrument this Terraform code with Datadog.