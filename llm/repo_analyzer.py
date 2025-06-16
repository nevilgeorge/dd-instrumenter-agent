import json
import logging
import os
from typing import Dict, List, Literal

import openai
from pydantic import BaseModel, Field

from util.document import Document
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
        
        prompt = f"""You are an expert at analyzing code repositories to determine their infrastructure type.
Analyze the following repository contents and determine if it's a CDK project, Terraform project, or neither.
If a CDK project is detected, look for the cdk.json file and the CDK app files.
If a Terraform project is detected, look for the .tf files, terraform.tfstate, and .tfvars files.
Also, look for the runtime of the Lambda function handler. If typeScript is detected, return node.js.

Look for key indicators:
- CDK: presence of cdk.json, CDK app files, aws-cdk-lib dependencies
- Terraform: .tf files, terraform.tfstate, .tfvars files

You must respond with ONLY a JSON object with the following keys only (no other text):
    - "repo_type": ["cdk", "terraform", "neither"],
    - "confidence": 0.95,
    - "evidence": ["Found cdk.json", "Found aws-cdk-lib dependency"]
    - "cdk_script_file": the name of the file that contains the CDK script (if detected), empty string if not detected
    - "terraform_script_file": the name of the file that contains the Terraform script (if detected), empty string if not detected
    - "runtime": the runtime of the Lambda function handler (if detected), empty string if not detected. One of ['node.js', 'python', 'java', 'go', 'ruby', 'dotnet']

The repo_type must be exactly one of: "cdk", "terraform", or "neither"
The confidence must be a number between 0 and 1
The evidence must be a list of strings

Repository contents:
{repo_contents}

Analyze this repository. Return ONLY the JSON object, no other text."""
        
        try:
            result_text = self.make_completion(prompt)
            result_dict = json.loads(result_text)
            
            return RepoType(**result_dict)
        except Exception as e:
            self.logger.error(f"Error analyzing repository: {str(e)}")
            raise 

    def filter_relevant_files(self, file_list: List[str], documentation: str, 
                            integration_name: str, integration_rules: str = "") -> RelevantFiles:
        """
        Filter files that are relevant for integration modifications.
        
        Args:
            file_list: List of file paths from the repository
            documentation: Installation documentation for reference
            integration_name: Name of the integration (e.g., "PostHog", "Datadog")
            integration_rules: Additional rules for filtering files
            
        Returns:
            RelevantFiles object containing filtered files and reasoning
        """
        # Format file list for the prompt
        formatted_file_list = "\n".join(file_list)
        
        prompt = f"""You are a {integration_name} installation wizard, a master AI programming assistant that implements {integration_name} for projects.
Given the following list of file paths from a project, determine which files are likely to require modifications 
to integrate {integration_name}. Use the installation documentation as a reference for what files might need modifications, do not include files that are unlikely to require modification based on the documentation.

- If you would like to create a new file, you can include the file path in your response.
- If you would like to modify an existing file, you can include the file path in your response.

You should return all files that you think will be required to look at or modify to integrate {integration_name}. You should return them in the order you would like to see them processed, with new files first, followed by the files that you want to update to integrate {integration_name}.

Rules:
- Only return files that you think will be required to look at or modify to integrate {integration_name}.
- Do not return files that are unlikely to require modification based on the documentation.
- If you are unsure, return the file, since it's better to have more files than less.
- If two files might include the content you need to edit, return both.
- If you create a new file, it should not conflict with any existing files.
- If the user is using TypeScript, you should return .ts and .tsx files.
- The file structure of the project may be different than the documentation, you should follow the file structure of the project. e.g. if there is an existing file containing providers, you should edit that file instead of creating a new one.
{integration_rules}
- Look for existing files that contain providers, components, hooks, etc. and edit those files instead of creating new ones if appropriate.

Installation documentation:
{documentation}

All current files in the repository:
{formatted_file_list}

You must respond with ONLY a JSON object with the following keys only (no other text):
    - "files_to_modify": ["file1.ts", "file2.js"] - existing files that need modification
    - "files_to_create": ["new_file.ts"] - new files that need to be created  
    - "reasoning": ["reason1", "reason2"] - explanations for each file selection

Return ONLY the JSON object, no other text."""

        try:
            result_text = self.make_completion(prompt)
            result_dict = json.loads(result_text)
            
            return RelevantFiles(**result_dict)
        except Exception as e:
            self.logger.error(f"Error filtering relevant files: {str(e)}")
            raise