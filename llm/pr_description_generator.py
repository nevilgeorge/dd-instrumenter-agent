import json
import logging
from typing import Dict, List

import openai
from pydantic import BaseModel, Field

from util.prompt_loader import load_prompt_template, parse_json_response
from llm import BaseLLMClient


class PRDescription(BaseModel):
    """Schema for PR description generation output."""

    title: str = Field(description="A concise title for the pull request")
    description: str = Field(description="A detailed description of the changes made")
    summary: List[str] = Field(description="List of key changes made in bullet points")


class PRDescriptionGenerator(BaseLLMClient):
    """
    Class responsible for generating PR descriptions using LangChain and OpenAI.
    Analyzes file changes and creates professional pull request descriptions.
    """

    def __init__(self, client: openai.OpenAI):
        """
        Initialize the PRDescriptionGenerator.

        Args:
            client: OpenAI client instance for PR description generation
        """
        super().__init__(client)

    def generate_description_from_diff(self, git_diff: str, file_names: List[str]) -> PRDescription:
        """
        Generate a PR description based on git diff output.

        Args:
            git_diff: Git diff output showing actual changes
            file_names: List of file names that were changed

        Returns:
            PRDescription containing title, description, and summary
        """
        prompt = load_prompt_template(
            "generate_pr_description",
            file_names=', '.join(file_names),
            git_diff=git_diff
        )

        try:
            result_text = self.make_completion(prompt)
            result_dict = parse_json_response(result_text)

            self.logger.debug("Successfully generated PR description from git diff")

            return PRDescription(**result_dict)
        except Exception as e:
            self.logger.error(f"Error generating PR description from diff: {str(e)}")
            # Fallback to a basic description
            return PRDescription(
                title="Instrument with Datadog",
                description="This PR adds Datadog monitoring and tracing instrumentation to AWS Lambda functions in the infrastructure code.",
                summary=[
                    "Added Datadog Lambda Extension layer",
                    "Added Datadog Tracing layer",
                    "Configured DD_ENV, DD_SERVICE, and DD_VERSION environment variables",
                ],
            )
