import subprocess
import os
from typing import List, Dict, Any
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.schema import Document

class RepoParser:
    """
    A class that encapsulates logic for parsing (or "processing") a repository, such as cloning it
    and reading its files using LangChain.
    """

    def clone_repository(self, clone_url: str, target_dir: str = "temp_clone") -> str:
        """
        Clone a repository from the given clone_url into a local folder.
        :param clone_url: (str) The clone URL (e.g. from the "clone_url" field of a repo response).
        :param target_dir: (str) (Optional) The target folder (defaults to "temp_clone").
        :return: (str) The absolute path of the cloned folder.
        """
        if os.path.exists(target_dir):
            import shutil
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)
        try:
            subprocess.run(["git", "clone", clone_url, target_dir], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to clone repository: {e.stderr}")
        return os.path.abspath(target_dir)

    def read_repository_files(self, repo_path: str, glob_pattern: str = "**/*") -> List[Document]:
        """
        Read files from the cloned repository using LangChain's DirectoryLoader.
        :param repo_path: (str) Path to the cloned repository
        :param glob_pattern: (str) Pattern to match files (default: all Python files)
        :return: List[Document] List of LangChain Document objects containing file contents
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
        :param documents: List[Document] List of LangChain Document objects to search through
        :param filename: str The name of the file to find
        :return: Document The matching Document object
        :raises: Exception if no matching document is found
        """
        for doc in documents:
            if os.path.basename(doc.metadata.get('source', '')) == filename:
                return doc
        raise Exception(f"Could not find document with filename: {filename}")









