import requests
import subprocess
import os
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class GithubClient:
    """
    A client to interact with the Github API with authentication.
    """
    BASE_URL = "https://api.github.com"

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the GithubClient with optional authentication.
        
        Args:
            github_token: Optional GitHub personal access token for authentication.
                         If not provided, will try to get from GITHUB_TOKEN env var.
        """
        self.token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.warning("No GitHub token provided. API requests will be rate-limited.")
        
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DD-Instrumenter-Agent/1.0"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make an authenticated request to the GitHub API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (will be appended to BASE_URL)
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response object from the request
            
        Raises:
            requests.exceptions.RequestException: If the request fails
            ValueError: If authentication fails
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        kwargs.setdefault('headers', {}).update(self.headers)
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            
            # Check for rate limiting
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining < 10:
                    logger.warning(f"GitHub API rate limit running low: {remaining} requests remaining")
            
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise ValueError("GitHub authentication failed. Please check your token.") from e
            elif e.response.status_code == 403:
                raise ValueError("GitHub API access forbidden. Please check your token permissions.") from e
            elif e.response.status_code == 404:
                raise ValueError(f"Repository not found: {url}") from e
            raise

    def read_repository(self, repository: str) -> Dict[str, Any]:
        """
        Fetch repository details from Github's API.
        
        Args:
            repository: str in the form 'owner/repo' or full GitHub URL
            
        Returns:
            JSON response from Github API
            
        Raises:
            ValueError: If authentication fails or repository is not found
            requests.exceptions.RequestException: For other API errors
        """
        # Handle full GitHub URLs
        if repository.startswith(('http://', 'https://')):
            # Extract owner/repo from URL
            parts = repository.rstrip('/').split('/')
            if len(parts) < 2:
                raise ValueError(f"Invalid GitHub URL format: {repository}")
            repository = f"{parts[-2]}/{parts[-1]}"
        
        try:
            response = self._make_request('GET', f"repos/{repository}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch repository {repository}: {str(e)}")
            raise

    def get_repository_contents(self, repository: str, path: str = "") -> Dict[str, Any]:
        """
        Get contents of a repository directory.
        
        Args:
            repository: str in the form 'owner/repo'
            path: str path within the repository (default: root)
            
        Returns:
            JSON response containing directory contents
            
        Raises:
            ValueError: If authentication fails or path is not found
            requests.exceptions.RequestException: For other API errors
        """
        try:
            response = self._make_request('GET', f"repos/{repository}/contents/{path}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch contents of {path} in {repository}: {str(e)}")
            raise
