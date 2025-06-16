import glob
import os
from typing import List

from util.document import Document


class RepoParser:
    """
    A class that encapsulates logic for parsing repository files.
    """

    def read_repository_files(self, repo_path: str, glob_pattern: str = "**/*") -> List[Document]:
        """
        Read files from the repository directory.

        Args:
            repo_path: Path to the repository directory
            glob_pattern: Pattern to match files (default: all files)

        Returns:
            List of Document objects containing file contents
        """
        try:
            documents = []
            pattern_path = os.path.join(repo_path, glob_pattern)

            for file_path in glob.glob(pattern_path, recursive=True):
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Create Document with content and metadata
                        doc = Document(
                            page_content=content,
                            metadata={
                                'source': file_path,
                                'filename': os.path.basename(file_path)
                            }
                        )
                        documents.append(doc)
                    except (UnicodeDecodeError, PermissionError):
                        # Skip binary files and files we can't read
                        continue

            return documents
        except Exception as e:
            raise Exception(f"Failed to read repository files: {str(e)}")

    def find_cdk_stack_file(self, documents: List[Document], runtime: str) -> Document:
        """
        Find the CDK stack file by looking for files that contain "extends cdk.Stack".
        :param documents: List[Document] List of Document objects to search through
        :return: Document The matching Document object containing the CDK stack definition
        :raises: Exception if no matching document is found
        """
        for doc in documents:
            if runtime == 'node.js':
                if "extends cdk.Stack" in doc.page_content:
                    return doc
            elif runtime == 'python':
                if "from aws_cdk import Stack" in doc.page_content:
                    return doc
            elif runtime == 'java':
                if "extends Stack" in doc.page_content:
                    return doc
            elif runtime == 'go':
                if "awscdk.NewStack" in doc.page_content:
                    return doc
            elif runtime == 'dotnet':
                if "using Amazon.CDK;" in doc.page_content:
                    return doc
            else:
                raise Exception(f"Unsupported runtime: {runtime}")
        raise Exception("Could not find any CDK stack file (no file contains 'extends cdk.Stack')")

    def find_terraform_file(self, documents: List[Document]) -> Document:
        """
        Find the main Terraform file by looking for files that contain Lambda function definitions.
        :param documents: List[Document] List of Document objects to search through
        :return: Document The matching Document object containing the Terraform configuration
        :raises: Exception if no matching document is found
        """
        # First try to find main.tf as it's the conventional entry point
        for doc in documents:
            if doc.metadata['filename'] == 'main.tf':
                return doc

        # If main.tf not found, look for any .tf file containing Lambda function definitions
        for doc in documents:
            if doc.metadata['filename'].endswith('.tf'):
                content = doc.page_content.lower()
                # Look for common Lambda function indicators in Terraform
                if any(indicator in content for indicator in [
                    'resource "aws_lambda_function"',  # Most specific pattern
                    'aws_lambda_function',  # Resource type
                    'lambda_function',  # Variable/parameter name
                    'lambda_layer',  # Lambda layer
                    'aws_lambda_permission',  # Lambda permissions
                    'aws_lambda_event_source_mapping',  # Event source mappings
                    'aws_lambda_alias',  # Lambda aliases
                    'aws_lambda_version'  # Lambda versions
                ]):
                    return doc

        # If no Lambda-specific file found, look for any .tf file that might contain provider configuration
        for doc in documents:
            if doc.metadata['filename'].endswith('.tf'):
                content = doc.page_content.lower()
                if 'provider "aws"' in content or 'terraform {' in content:
                    return doc

        raise Exception("Could not find any Terraform file containing Lambda function definitions or AWS provider configuration")
