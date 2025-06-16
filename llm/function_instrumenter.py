import json
import logging
from typing import Dict, List, Literal

import openai
from pydantic import BaseModel, Field

from util.document import Document
from util.document_retriever import DocSection


class InstrumentationResult(BaseModel):
    """Schema for instrumentation output."""
    file_changes: Dict[str, str] = Field(description="Map of file paths to their modified contents with Datadog instrumentation")
    instrumentation_type: Literal["datadog_lambda_instrumentation"] = Field(
        description="Type of instrumentation added",
        default="datadog_lambda_instrumentation"
    )

class FunctionInstrumenter:
    """Class responsible for instrumenting AWS Lambda functions with Datadog."""

    def __init__(self, client: openai.OpenAI):
        """
        Initialize the FunctionInstrumenter.

        Args:
            client: OpenAI client instance for code analysis and modification
        """
        self.client = client
        self.logger = logging.getLogger(__name__)

    def instrument_cdk_file(self, cdk_script_file: Document, dd_documentation: Dict[str, DocSection]) -> InstrumentationResult:
        """
        Instrument a CDK file with Datadog Lambda instrumentation.

        Args:
            cdk_script_file: Document containing CDK file content
            dd_documentation: Datadog documentation sections

        Returns:
            InstrumentationResult containing the modified code and change information
        """
        prompt = f"""You are an expert at instrumenting AWS CDK code with Datadog.
Your task is to analyze and modify CDK code to add Datadog instrumentation to all Lambda functions.

Key requirements:
- Add Datadog Lambda Extension layer to all Lambda functions
- Add Datadog Tracing layer to all Lambda functions
- Set DD_ENV, DD_SERVICE, and DD_VERSION environment variables
- Add necessary imports for Datadog
- Ensure proper error handling
- Maintain existing functionality
- Follow AWS CDK best practices

For each Lambda function, you must:
1. Add the Datadog Lambda Extension layer (arn:aws:lambda:{{region}}:464622532012:layer:Datadog-Extension:latest)
2. Add the Datadog Tracing layer (arn:aws:lambda:{{region}}:464622532012:layer:dd-trace-py:latest)
3. Set environment variables:
   - DD_ENV: based on the stack environment
   - DD_SERVICE: based on the function name
   - DD_VERSION: based on the stack version or '1.0.0' if not specified

You must respond with ONLY a JSON object containing:
{{
    "file_changes": {{"file_path": "new file content"}},
    "instrumentation_type": "datadog_lambda_instrumentation"
}}

Instrument this CDK code with Datadog:
{cdk_script_file.page_content}"""

        try:
            response = self.client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                stream=False,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.choices[0].message.content
            result_dict = json.loads(result_text)

            self.logger.debug(f"Successfully instrumented CDK file with Datadog: {cdk_script_file.metadata['source']}")
            return InstrumentationResult(**result_dict)
        except Exception as e:
            self.logger.error(f"Error instrumenting CDK file {cdk_script_file.metadata['source']}: {str(e)}")
            raise

    def instrument_terraform_file(self, file_path: str, code: str) -> InstrumentationResult:
        """
        Instrument a Terraform file with Datadog Lambda instrumentation.

        Args:
            file_path: Path to the Terraform file
            code: Content of the Terraform file

        Returns:
            InstrumentationResult containing the modified code and change information
        """
        prompt = f"""You are an expert at instrumenting Terraform code with Datadog.
Your task is to analyze and modify Terraform code to add Datadog instrumentation to all Lambda functions.

Key requirements:
- Add Datadog Lambda Extension layer to all Lambda functions
- Add Datadog Tracing layer to all Lambda functions
- Set DD_ENV, DD_SERVICE, and DD_VERSION environment variables
- Add necessary provider configurations
- Ensure proper error handling
- Maintain existing functionality
- Follow Terraform best practices

For each Lambda function, you must:
1. Add the Datadog Lambda Extension layer (arn:aws:lambda:{{region}}:464622532012:layer:Datadog-Extension:latest)
2. Add the Datadog Tracing layer (arn:aws:lambda:{{region}}:464622532012:layer:dd-trace-py:latest)
3. Set environment variables:
   - DD_ENV: based on the environment variable or 'dev' if not specified
   - DD_SERVICE: based on the function name
   - DD_VERSION: based on the version variable or '1.0.0' if not specified

You must respond with ONLY a JSON object containing:
{{
    "modified_code": "the complete modified code with Datadog instrumentation",
    "changes_made": ["list of specific changes made to each Lambda function"],
    "instrumentation_type": "datadog_lambda_instrumentation"
}}

Instrument this Terraform code with Datadog:
{code}"""

        try:
            response = self.client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                stream=False,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.choices[0].message.content
            result_dict = json.loads(result_text)

            self.logger.debug(f"Successfully instrumented Terraform file with Datadog: {file_path}")
            return InstrumentationResult(**result_dict)
        except Exception as e:
            self.logger.error(f"Error instrumenting Terraform file {file_path}: {str(e)}")
            raise
