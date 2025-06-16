import json
import logging
from typing import Dict, List, Literal

import openai
from pydantic import BaseModel, Field

from util.document import Document
from util.document_retriever import DocSection
from llm import BaseLLMClient


class InstrumentationResult(BaseModel):
    """Schema for instrumentation output."""
    file_changes: Dict[str, str] = Field(description="Map of file paths to their modified contents with Datadog instrumentation")
    instrumentation_type: Literal["datadog_lambda_instrumentation"] = Field(
        description="Type of instrumentation added",
        default="datadog_lambda_instrumentation"
    )

class FunctionInstrumenter(BaseLLMClient):
    """Class responsible for instrumenting AWS Lambda functions with Datadog."""

    def __init__(self, client: openai.OpenAI):
        """
        Initialize the FunctionInstrumenter.

        Args:
            client: OpenAI client instance for code analysis and modification
        """
        super().__init__(client)

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
            Do not return a diff — you should return the entire, COMPLETE file content without any abbreviations / sections omitted.

            Rules:
            - Preserve the existing code formatting and style.
            - Only make the changes required by the documentation.
            - If no changes are needed, return the file as-is.
            - If the current file is empty, and you think it should be created, you can add the contents of the new file.
            - The file structure of the project may be different than the documentation, you should follow the file structure of the project.
            - Use relative imports if you are unsure what the project import paths are.
            - It's okay not to edit a file if it's not needed (e.g. if you have already edited another one or this one is not needed).
            - Return the full, final modified code in file_changes

            You must respond with ONLY a dict object containing (do not format as json):
            {{
                "file_changes": {{
                    "{cdk_script_file.metadata['source']}": "the complete modified file content"
                }},
                "instrumentation_type": "datadog_lambda_instrumentation"
            }}

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

            ---

            Instrument this CDK code with Datadog.
"""
        
        try:
            result_text = self.make_completion(prompt)
            result_dict = json.loads(result_text)

            self.logger.info(f"Successfully instrumented CDK file with Datadog: {cdk_script_file.metadata['source']}")
            return InstrumentationResult(**result_dict)
        except Exception as e:
            self.logger.error(f"Error instrumenting CDK file {cdk_script_file.metadata['source']}: {str(e)}")
            raise

    def instrument_terraform_file(self, file_path: str, code: str, dd_documentation: Dict[str, DocSection], additional_context: str) -> InstrumentationResult:
        """
        Instrument a Terraform file with Datadog Lambda instrumentation.

        Args:
            file_path: Path to the Terraform file
            code: Content of the Terraform file
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

        Your task is to analyze and modify Terraform code to install Datadog according to the documentation.
        Do not return a diff — you should return the entire, COMPLETE file content without any abbreviations / sections omitted.

        Rules:
        - Preserve the existing code formatting and style.
        - Only make the changes required by the documentation.
        - If no changes are needed, return the file as-is.
        - If the current file is empty, and you think it should be created, you can add the contents of the new file.
        - The file structure of the project may be different than the documentation, you should follow the file structure of the project.
        - Use relative imports if you are unsure what the project import paths are.
        - It's okay not to edit a file if it's not needed (e.g. if you have already edited another one or this one is not needed).
        - Return the full, final modified code in file_changes
        - Follow Terraform best practices

        You must respond with ONLY a dict object containing (do not format as json):
        {{
        "file_changes": {{
            "{file_path}": "the complete modified file content"
        }},
        "instrumentation_type": "datadog_lambda_instrumentation"
        }}

        CONTEXT
        ---

        Documentation for installing Datadog on AWS Lambda:
        {formatted_docs}

        The file you are updating is:
        {file_path}

        The code in the file, which you must modify to install Datadog, is the following:
        {code}

        Also consider the following optional customization instructions from the user:
        {additional_context}

        ---

        Instrument this Terraform code with Datadog:"""

        try:
            result_text = self.make_completion(prompt)
            result_dict = json.loads(result_text)

            self.logger.info(f"Successfully instrumented Terraform file with Datadog: {file_path}")
            return InstrumentationResult(**result_dict)
        except Exception as e:
            self.logger.error(f"Error instrumenting Terraform file {file_path}: {str(e)}")
            raise