import requests
import os
import time
import subprocess
import shutil
from typing import Any, Dict, Optional
from llm.pr_description_generator import PRDescriptionGenerator, PRDescription
from llm.function_instrumenter import InstrumentationResult
import logging
from git import Repo
from github import Github
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
        self.logger = logging.getLogger(__name__)

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

    def clone_repository(self, clone_url: str, target_dir: str = "temp_clone") -> str:
        """
        Clone a repository from the given clone_url into a local folder.

        Args:
            clone_url: The clone URL (e.g. from the "clone_url" field of a repo response)
            target_dir: The target folder (defaults to "temp_clone")

        Returns:
            The absolute path of the cloned folder
        """
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", clone_url, target_dir],
                check=True,
                capture_output=True,
                text=True
            )
            self.logger.info(f"Successfully cloned repository to {target_dir}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to clone repository: {e.stderr}")
            raise Exception(f"Failed to clone repository: {e.stderr}")
        return os.path.abspath(target_dir)

    def _create_branch_and_commit(
        self,
        repo_path: str,
        branch_name: str,
        file_changes: Dict[str, str],
    ) -> None:
        """
        Create a new branch and commit the file changes.

        Args:
            repo_path: Path to the git repository
            branch_name: Name of the new branch to create
            file_changes: Dictionary mapping file names to their new contents
            commit_message: Commit message for the changes
        """
        try:
            # Initialize git repo
            repo = Repo(repo_path)

            # Create and checkout new branch
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()
            self.logger.info(f"Created and checked out branch: {branch_name}")

            # Write the changed files
            for filename, content in file_changes.items():
                file_path = os.path.join(repo_path, filename)

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.logger.info(f"Updated file: {filename}")

            # Stage all changes
            repo.git.add(A=True)

            # Commit changes
            repo.index.commit("Instrumented with Datadog")
        except Exception as e:
            self.logger.error(f"Git operation failed: {str(e)}")
            raise Exception(f"Failed to create branch and commit: {str(e)}")

    def _push_branch(self, repo_path: str, branch_name: str) -> None:
        """
        Push the branch to the remote repository.

        Args:
            repo_path: Path to the git repository
            branch_name: Name of the branch to push
        """
        try:
            repo = Repo(repo_path)
            origin = repo.remote(name="origin")
            origin.push(branch_name, set_upstream=True)
            self.logger.info(f"Pushed branch {branch_name} to origin")

        except Exception as e:
            self.logger.error(f"Failed to push branch: {str(e)}")
            raise Exception(f"Failed to push branch {branch_name}: {str(e)}")

    def _create_pull_request(
        self,
        repo_owner: str,
        repo_name: str,
        branch_name: str,
        pr_description: PRDescription,
        base_branch: str = "main",
    ) -> Dict:
        """
        Create a pull request using GitHub API.

        Args:
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            branch_name: Name of the source branch
            pr_description: Generated PR description
            base_branch: Base branch for the PR (default: main)

        Returns:
            Dictionary containing PR information
        """
        try:
            if not self.github:
                raise Exception("GitHub token not provided")

            # Get the repository
            repo = self.github.get_repo(f"{repo_owner}/{repo_name}")

            # Format the PR body
            pr_body = f"""{pr_description.description}

## Changes Made
{chr(10).join(f"- {item}" for item in pr_description.summary)}

---
*This PR was generated automatically by the DD Instrumenter Agent*"""

            # Create pull request
            pr = repo.create_pull(
                title=pr_description.title,
                body=pr_body,
                head=branch_name,
                base=base_branch,
            )

            self.logger.info(f"Created pull request: {pr.html_url}")

            return {
                "pr_url": pr.html_url,
                "pr_number": pr.number,
                "title": pr_description.title,
                "branch": branch_name,
                "status": "created",
            }

        except Exception as e:
            self.logger.error(f"Failed to create pull request: {str(e)}")
            raise Exception(f"Failed to create pull request: {str(e)}")

    def _get_git_diff(self, repo_path: str, base_branch: str = "main") -> str:
        """
        Get git diff between current branch and base branch.

        Args:
            repo_path: Path to the git repository
            base_branch: Base branch to compare against (default: main)

        Returns:
            String containing the git diff output
        """
        try:
            repo = Repo(repo_path)

            # Get diff between base branch and current branch
            diff = repo.git.diff(f"{base_branch}...HEAD")

            return diff

        except Exception as e:
            self.logger.error(f"Failed to get git diff: {str(e)}")
            raise Exception(f"Failed to get git diff: {str(e)}")

    def generate_pull_request(
        self,
        repo_path: str,
        repo_owner: str,
        repo_name: str,
        instrumentation_result: InstrumentationResult,
        pr_generator: PRDescriptionGenerator,
        branch_name: str = None,
        base_branch: str = "main",
    ) -> Dict:
        """
        Complete workflow to generate a pull request with the given instrumentation changes.

        Args:
            repo_path: Path to the git repository
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            instrumentation_result: InstrumentationResult containing file changes and metadata
            pr_generator: PRDescriptionGenerator instance for creating descriptions
            branch_name: Optional custom branch name (auto-generated if not provided)
            base_branch: Base branch to compare against (default: main)

        Returns:
            Dictionary containing PR information and status
        """
        try:
            # Generate branch name if not provided
            if not branch_name:
                timestamp = int(time.time())
                branch_name = f"feature/datadog-instrumentation-{timestamp}"

            # Extract file changes from instrumentation result
            file_changes = instrumentation_result.file_changes

            # Create branch and commit changes first
            self.logger.info(f"Creating branch {branch_name} and committing changes...")
            self._create_branch_and_commit(
                repo_path, branch_name, file_changes
            )

            # Get git diff for better context
            self.logger.info("Getting git diff for PR description generation...")
            git_diff = self._get_git_diff(repo_path, base_branch)

            # Generate PR description using the actual diff
            self.logger.info("Generating PR description from git diff...")
            pr_description = pr_generator.generate_description_from_diff(
                git_diff, list(file_changes.keys())
            )

            # Push branch to remote
            self.logger.info("Pushing branch to remote...")
            self._push_branch(repo_path, branch_name)

            # Create pull request
            self.logger.info("Creating pull request...")
            pr_info = self._create_pull_request(
                repo_owner, repo_name, branch_name, pr_description, base_branch
            )

            return {
                **pr_info,
                "files_changed": list(file_changes.keys()),
                "commit_message": pr_description.title,
                "instrumentation_type": instrumentation_result.instrumentation_type,
            }

        except Exception as e:
            self.logger.error(f"Failed to generate pull request: {str(e)}")
            raise Exception(f"Pull request generation failed: {str(e)}")
