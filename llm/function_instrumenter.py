import json
from typing import Dict, Literal

import openai
from pydantic import BaseModel, Field

from util.document import Document
from util.document_retriever import DocSection
from util.prompt_loader import load_prompt_template, parse_json_response
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

    def instrument_cdk_file(self, cdk_script_file: Document, dd_documentation: Dict[str, DocSection], runtime: str, additional_context: str) -> InstrumentationResult:
        """
        Instrument a CDK file with Datadog Lambda instrumentation.

        Args:
            cdk_script_file: Document containing CDK file content
            dd_documentation: Datadog documentation sections
            runtime: Programming language runtime (e.g., "python", "nodejs", "java")

        Returns:
            InstrumentationResult containing the modified code and change information
        """
        # Format documentation sections into a readable string
        formatted_docs = "\n\n".join([
            f"Section: {section_name}\n{section.content}"
            for section_name, section in dd_documentation.items()
        ])

        prompt = load_prompt_template(
            "instrument",
            file_type="CDK stack",
            formatted_docs=formatted_docs,
            file_path=cdk_script_file.metadata['source'],
            file_content=cdk_script_file.page_content,
            runtime=runtime,
            additional_context=additional_context,
        )

        try:
            result_text = self.make_completion(prompt)

            self.logger.info(f"🔍 OpenAI response length: {len(result_text) if result_text else 0}")
            self.logger.info(f"🔍 OpenAI response preview: {result_text[:200] if result_text else 'None'}...")

            if not result_text or not result_text.strip():
                raise ValueError("OpenAI returned empty response")


            result_dict = parse_json_response(result_text)

            self.logger.info(f"Successfully instrumented CDK file with Datadog: {cdk_script_file.metadata['source']}")
            return InstrumentationResult(**result_dict)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error for CDK file {cdk_script_file.metadata['source']}: {str(e)}")
            self.logger.error(f"Raw OpenAI response: {result_text if 'result_text' in locals() else 'No response'}")
            raise ValueError(f"Failed to parse OpenAI response as JSON: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error instrumenting CDK file {cdk_script_file.metadata['source']}: {str(e)}")
            raise

    def instrument_terraform_file(self, file_path: str, code: str, dd_documentation: Dict[str, DocSection], runtime: str, additional_context: str) -> InstrumentationResult:
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

        prompt = load_prompt_template(
           "instrument",
            file_type="Terraform",
            formatted_docs=formatted_docs,
            file_path=file_path,
            file_content=code,
            runtime="",
            additional_context=additional_context,
        )

        try:
            result_text = self.make_completion(prompt)
            result_dict = parse_json_response(result_text)

            self.logger.info(f"Successfully instrumented Terraform file with Datadog: {file_path}")
            return InstrumentationResult(**result_dict)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error for Terraform file {file_path}: {str(e)}")
            self.logger.error(f"Raw OpenAI response: {result_text if 'result_text' in locals() else 'No response'}")
            raise ValueError(f"Failed to parse OpenAI response as JSON: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error instrumenting Terraform file {file_path}: {str(e)}")
            raise
