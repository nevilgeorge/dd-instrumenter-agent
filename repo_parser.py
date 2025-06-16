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

    def find_document_by_filename(self, documents: List[Document], filename: str) -> Document:
        """
        Find a specific Document from a list of Documents by matching the filename.

        Args:
            documents: List of LangChain Document objects to search through
            filename: The name of the file to find

        Returns:
            The matching Document object

        Raises:
            Exception if no matching document is found
        """
        for doc in documents:
            if os.path.basename(doc.metadata.get('source', '')) == filename:
                return doc
        raise Exception(f"Could not find document with filename: {filename}")
