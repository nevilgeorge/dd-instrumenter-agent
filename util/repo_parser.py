import glob
import os
from typing import List, Dict, Any

from util.document import Document


class RepoParser:
    """
    A class that encapsulates logic for parsing repository files.
    """

    def read_repository_files(self, repo_path: str, glob_pattern: str = "**/*") -> Dict[str, Any]:
        """
        Read files from the repository directory and build a tree structure.

        Args:
            repo_path: Path to the repository directory
            glob_pattern: Pattern to match files (default: all files)

        Returns:
            Dict representing the repository tree structure
        """
        try:
            tree = {}
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
                        
                        # Build tree structure
                        rel_path = os.path.relpath(file_path, repo_path)
                        self._add_to_tree(tree, rel_path, doc)
                        
                    except (UnicodeDecodeError, PermissionError):
                        # Skip binary files and files we can't read
                        continue

            return tree
        except Exception as e:
            raise Exception(f"Failed to read repository files: {str(e)}")

    def _add_to_tree(self, tree: Dict[str, Any], path: str, doc: Document) -> None:
        """
        Add a document to the tree structure at the specified path.
        """
        parts = path.split(os.sep)
        current = tree
        
        # Navigate/create directories
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Add the file
        current[parts[-1]] = doc


    def _get_all_documents(self, tree: Dict[str, Any]) -> List[Document]:
        """
        Get all Document objects from the tree structure.
        """
        documents = []
        
        def traverse(node):
            if isinstance(node, Document):
                documents.append(node)
            elif isinstance(node, dict):
                for value in node.values():
                    traverse(value)
        
        traverse(tree)
        return documents
