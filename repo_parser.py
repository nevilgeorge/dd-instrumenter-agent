import os
from typing import List, Dict, Any
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.schema import Document

class RepoParser:
    """
    A class that encapsulates logic for parsing repository files using LangChain.
    """

    def read_repository_files(self, repo_path: str, glob_pattern: str = "**/*") -> List[Document]:
        """
        Read files from the repository using LangChain's DirectoryLoader.

        Args:
            repo_path: Path to the repository directory
            glob_pattern: Pattern to match files (default: all files)

        Returns:
            List of LangChain Document objects containing file contents
        """
        try:
            loader = DirectoryLoader(
                repo_path,
                glob=glob_pattern,
                loader_cls=TextLoader,
                show_progress=True
            )
            documents = loader.load()
            return documents
        except Exception as e:
            raise Exception(f"Failed to read repository files: {str(e)}")
    
    def find_cdk_stack_file(self, documents: List[Document], runtime: str) -> Document:
        """
        Find the CDK stack file by looking for files that contain "extends cdk.Stack".
        :param documents: List[Document] List of LangChain Document objects to search through
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
