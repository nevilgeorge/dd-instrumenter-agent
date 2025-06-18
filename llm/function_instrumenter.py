import json
from typing import Dict, Literal, List

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
    next_steps: List[str] = Field(description="List of steps required after instrumentation", default_factory=list)
    docs_urls: List[str] = Field(description="List of documentation URLs used to generate this instrumentation", default_factory=list)

class FunctionInstrumenter(BaseLLMClient):
    """Class responsible for instrumenting AWS Lambda functions with Datadog."""

    def __init__(self, client: openai.OpenAI):
        """
        Initialize the FunctionInstrumenter.

        Args:
            client: OpenAI client instance for code analysis and modification
        """
        super().__init__(client)

    def instrument_file(self, file_path: str, file_type: str, dd_documentation: DocSection, runtime: str, additional_context: str = "") -> InstrumentationResult:
        """
        Instrument a file with Datadog Lambda instrumentation.

        Args:
            file_path: Path to the file to instrument
            file_type: Type of file (e.g., "CDK", "Terraform")
            dd_documentation: Datadog documentation
            runtime: Programming language runtime
            additional_context: Optional additional context from the user

        Returns:
            InstrumentationResult containing the modified code and change information
        """
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        prompt = load_prompt_template(
            "instrument",
            file_type=file_type,
            documentation=dd_documentation,
            file_path=file_path,
            file_content=file_content,
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

            # Add the documentation URL to the result
            if dd_documentation and hasattr(dd_documentation, 'url'):
                result_dict['docs_urls'] = [dd_documentation.url]

            self.logger.info(f"Successfully instrumented {file_type} file with Datadog: {file_path}")
            return InstrumentationResult(**result_dict)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error for {file_type} file {file_path}: {str(e)}")
            self.logger.error(f"Raw OpenAI response: {result_text if 'result_text' in locals() else 'No response'}")
            raise ValueError(f"Failed to parse OpenAI response as JSON: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error instrumenting {file_type} file {file_path}: {str(e)}")
            raise

    def instrument_cdk_file(self, file_path: str, dd_documentation: DocSection, runtime: str, additional_context: str = "") -> InstrumentationResult:
        """Instrument a CDK file with Datadog Lambda instrumentation."""
        return self.instrument_file(file_path, "CDK stack", dd_documentation, runtime, additional_context)

    def instrument_terraform_file(self, file_path: str, dd_documentation: DocSection, runtime: str, additional_context: str = "") -> InstrumentationResult:
        """Instrument a Terraform file with Datadog Lambda instrumentation."""
        return self.instrument_file(file_path, "Terraform", dd_documentation, runtime, additional_context)
