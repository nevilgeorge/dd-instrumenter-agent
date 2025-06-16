import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.schema import Document

class FileSystemUtils:
    """
    Utility class for reading and processing files and directories using LangChain.
    Provides methods for loading documents from file systems and searching through them.
    """

    def load_documents_from_directory(self, directory_path: str, glob_pattern: str = "**/*") -> List[Document]:
        """
        Load files from a directory using LangChain's DirectoryLoader.

        Args:
            directory_path: Path to the directory to read
            glob_pattern: Pattern to match files (default: all files)

        Returns:
            List of LangChain Document objects containing file contents
        """
        try:
            loader = DirectoryLoader(
                directory_path,
                glob=glob_pattern,
                loader_cls=TextLoader,
                show_progress=True
            )
            documents = loader.load()
            return documents
        except Exception as e:
            raise Exception(f"Failed to load documents from directory: {str(e)}")

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
