import requests
import subprocess
import os
from typing import Any, Dict

class GithubClient:
    """
    A simple client to interact with the Github API.
    """
    BASE_URL = "https://api.github.com"

    def read_repository(self, repository: str) -> Dict[str, Any]:
        """
        Fetch repository details from Github's API.
        :param repository: str in the form 'owner/repo'
        :return: JSON response from Github API
        """
        url = f"{self.BASE_URL}/repos/{repository}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
