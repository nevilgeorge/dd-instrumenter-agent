from typing import Dict, List
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import logging


class PRDescription(BaseModel):
    """Schema for PR description generation output."""

    title: str = Field(description="A concise title for the pull request")
    description: str = Field(description="A detailed description of the changes made")
    summary: List[str] = Field(description="List of key changes made in bullet points")


class PRDescriptionGenerator:
    """
    Class responsible for generating PR descriptions using LangChain and OpenAI.
    Analyzes file changes and creates professional pull request descriptions.
    """

    def __init__(self, llm: ChatOpenAI):
        """
        Initialize the PRDescriptionGenerator.

        Args:
            llm: ChatOpenAI instance for PR description generation
        """
        self.llm = llm
        self.logger = logging.getLogger(__name__)

        # Create output parser
        self.output_parser = PydanticOutputParser(pydantic_object=PRDescription)

        # Create prompt template for PR description generation
        self.description_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert at creating clear, professional pull request descriptions for infrastructure code changes.
            Your task is to analyze the file changes and generate a comprehensive PR description that explains what was modified and why.

            Focus on:
            - Clear, concise title that summarizes the main change
            - Detailed description explaining the purpose of the changes
            - Key technical changes made to each file
            - Benefits of the instrumentation added

            The changes involve adding Datadog instrumentation to Lambda functions in Infrastructure as Code (IaC) files.

            You must respond with ONLY a JSON object containing:
            {{
                "title": "A concise title for the pull request",
                "description": "A comprehensive description explaining the changes and their purpose",
                "summary": ["List of key changes made in bullet points"]
            }}

            {format_instructions}
            """,
                ),
                (
                    "human",
                    """Analyze these file changes and generate a PR description:

                    Files changed:
                    {file_changes}

                    Generate a professional PR description for these Datadog instrumentation changes.""",
                ),
            ]
        )

        # Create chain for description generation
        self.description_chain = LLMChain(
            llm=self.llm,
            prompt=self.description_prompt,
            output_parser=self.output_parser,
            verbose=True,
        )

    def generate_description_from_diff(self, git_diff: str, file_names: List[str]) -> PRDescription:
        """
        Generate a PR description based on git diff output.

        Args:
            git_diff: Git diff output showing actual changes
            file_names: List of file names that were changed

        Returns:
            PRDescription containing title, description, and summary
        """
        try:
            # Create a specialized prompt for git diff analysis
            diff_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        """You are an expert at creating clear, professional pull request descriptions for infrastructure code changes.
            Your task is to analyze the git diff and generate a comprehensive PR description that explains what was modified and why.

            Focus on:
            - Clear, concise title that summarizes the main change
            - Detailed description explaining the purpose of the changes
            - Key technical changes made to each file based on the diff
            - Benefits of the instrumentation added

            The changes involve adding Datadog instrumentation to Lambda functions in Infrastructure as Code (IaC) files.

            You must respond with ONLY a JSON object containing:
            {{
                "title": "A concise title for the pull request",
                "description": "A comprehensive description explaining the changes and their purpose",
                "summary": ["List of key changes made in bullet points"]
            }}

            {format_instructions}
            """,
                    ),
                    (
                        "human",
                        """Analyze this git diff and generate a PR description:

Files changed: {file_names}

Git diff:
{git_diff}

Generate a professional PR description for these Datadog instrumentation changes based on the actual diff.""",
                    ),
                ]
            )

            # Create a temporary chain for diff analysis
            diff_chain = LLMChain(
                llm=self.llm,
                prompt=diff_prompt,
                output_parser=self.output_parser,
                verbose=True,
            )

            result = diff_chain.invoke(
                {
                    "git_diff": git_diff,
                    "file_names": ", ".join(file_names),
                    "format_instructions": self.output_parser.get_format_instructions(),
                }
            )

            self.logger.info("Successfully generated PR description from git diff")
            return result["text"]
        except Exception as e:
            self.logger.error(f"Error generating PR description from diff: {str(e)}")
            # Fallback to a basic description
            return PRDescription(
                title="Add Datadog instrumentation to Lambda functions",
                description="This PR adds Datadog monitoring and tracing instrumentation to AWS Lambda functions in the infrastructure code.",
                summary=[
                    "Added Datadog Lambda Extension layer",
                    "Added Datadog Tracing layer",
                    "Configured DD_ENV, DD_SERVICE, and DD_VERSION environment variables",
                ],
            )
