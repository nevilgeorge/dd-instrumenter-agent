from typing import Dict, List, Literal
from pydantic import BaseModel, Field
import logging
import json
import openai
from util.document_retriever import DocSection
from util.document import Document

class InstrumentationResult(BaseModel):
    """Schema for instrumentation output."""
    modified_code: str = Field(description="The complete modified code with Datadog instrumentation")
    changes_made: List[str] = Field(description="List of specific changes made to each Lambda function")
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
    
    def instrument_cdk_file(self, cdk_script_file: Document, dd_documentation: Dict[str, DocSection], additional_context: str) -> InstrumentationResult:
        """
        Instrument a CDK file with Datadog Lambda instrumentation.
        
        Args:
            cdk_script_file: Document containing CDK file content
            dd_documentation: Datadog documentation sections
            additional_context: Optional additional context from the user
            
        Returns:
            InstrumentationResult containing the modified code and change information
        """
        # Format documentation sections into a readable string
        formatted_docs = "\n\n".join([
            f"Section: {section_name}\n{section.content}"
            for section_name, section in dd_documentation.items()
        ])

        prompt = f"""You are a Datadog Monitoring installation wizard, a master AI programming
            assistant that installs Datadog Monitoring (metrics, logs, traces) to any
            AWS Lambda function. You install the Datadog Lambda Extension and Datadog
            Tracing layer to all Lambda functions. You also set the DD_ENV, DD_SERVICE,
            and DD_VERSION environment variables.

            Your task is to update the CDK stack file to install Datadog according to the documentation.
            Do not return a diff — you should return the complete updated file content.

            Rules:
            - Preserve the existing code formatting and style.
            - Only make the changes required by the documentation.
            - If no changes are needed, return the file as-is.
            - If the current file is empty, and you think it should be created, you can add the contents of the new file.
            - The file structure of the project may be different than the documentation, you should follow the file structure of the project.
            - Use relative imports if you are unsure what the project import paths are.
            - It's okay not to edit a file if it's not needed (e.g. if you have already edited another one or this one is not needed).

            You must respond with ONLY a JSON object containing the following fields:
                - "modified_code": "the complete modified code with Datadog instrumentation",
                - "changes_made": ["list of specific changes made to each Lambda function"],
                - "instrumentation_type": "datadog_lambda_instrumentation"

            CONTEXT
            ---

            Documentation for installing Datadog on AWS Lambda:
            {formatted_docs}

            The file you are updating is:
            {cdk_script_file.metadata['source']}

            The code in the file, which you must modify to install Datadog, is the following:
            {cdk_script_file.page_content}

            Also consider the following optional customization instructions from the user:
            {additional_context}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                stream=False,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.choices[0].message.content
            result_dict = json.loads(result_text)
            
            self.logger.info(f"Successfully instrumented CDK file with Datadog: {cdk_script_file.metadata['source']}")
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
            
            self.logger.info(f"Successfully instrumented Terraform file with Datadog: {file_path}")
            return InstrumentationResult(**result_dict)
        except Exception as e:
            self.logger.error(f"Error instrumenting Terraform file {file_path}: {str(e)}")
            raise 