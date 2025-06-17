import os
from typing import List, Literal

import openai
from pydantic import BaseModel, Field

from util.document import Document
from util.prompt_loader import load_prompt_template, parse_json_response
from llm import BaseLLMClient


class RepoType(BaseModel):
    """Schema for repository type analysis output."""
    repo_type: Literal["cdk", "terraform", "neither"] = Field(description="The type of infrastructure as code project")
    confidence: float = Field(description="Confidence score between 0 and 1")
    evidence: List[str] = Field(description="List of evidence found in the repository that led to this conclusion")
    cdk_script_file: str = Field(description="The name of the file that contains the CDK script")
    terraform_script_file: str = Field(description="The name of the file that contains the Terraform script")
    runtime: str = Field(description="The runtime of the Lambda function")


class RelevantFiles(BaseModel):
    """Schema for relevant files analysis output."""
    files_to_modify: List[str] = Field(description="List of file paths that need to be modified")
    files_to_create: List[str] = Field(description="List of new file paths that need to be created")
    reasoning: List[str] = Field(description="List of reasoning for why each file was selected")

class RepoAnalyzer(BaseLLMClient):
    """
    Analyzes repository contents to determine if it's a CDK, Terraform, or neither.
    Uses LangChain and OpenAI to perform the analysis.
    """

    def __init__(self, client: openai.OpenAI):
        """
        Initialize the RepoAnalyzer.

        Args:
            client: OpenAI client instance for repository analysis
        """
        super().__init__(client)

    def analyze_repo(self, documents: List[Document]) -> RepoType:
        """
        Analyze repository contents to determine its type.
        :param documents: List of LangChain Document objects containing repository contents
        :return: RepoType object containing the analysis results
        """
        # Format repository contents for the prompt
        repo_contents = "\n".join([
            f"File: {os.path.basename(doc.metadata.get('source', 'unknown'))}\n---"
            for doc in documents
        ])

        prompt = load_prompt_template(
            "analyze_repo",
            repo_contents=repo_contents
        )

        try:
            result_text = self.make_completion(prompt)
            result_dict = parse_json_response(result_text)
            return RepoType(**result_dict)
        except Exception as e:
            self.logger.error(f"Error analyzing repository: {str(e)}")
            raise
