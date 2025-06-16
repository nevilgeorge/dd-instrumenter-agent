import requests
import os
import time
import subprocess
import shutil
from typing import Any, Dict
from pr_description_generator import PRDescriptionGenerator, PRDescription
from function_instrumenter import InstrumentationResult
import logging
from git import Repo
from github import Github


class GithubClient:
    """
    A client to interact with the Github API and perform git operations.
    Handles repository operations, branch management, and PR creation.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, github_token: str = None):
        """
        Initialize the GithubClient.

        Args:
            github_token: GitHub personal access token for API access
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.logger = logging.getLogger(__name__)

        # Initialize GitHub API client
        if self.github_token:
            self.github = Github(self.github_token)
        else:
            self.github = None
            self.logger.warning(
                "No GitHub token provided. PR creation will require manual authentication."
            )

    def read_repository(self, repository: str) -> Dict[str, Any]:
        """
        Fetch repository details from Github's API.
        :param repository: str in the form 'owner/repo'
        :return: JSON response from Github API
        """
        url = f"{self.BASE_URL}/repos/{repository}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()

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
