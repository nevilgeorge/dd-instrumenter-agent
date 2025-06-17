import logging
import os
import shutil
import time
from typing import Any, Dict, Optional

from git import Repo
from github import Github
from github.GithubException import GithubException

from llm.function_instrumenter import InstrumentationResult
from llm.pr_description_generator import PRDescription, PRDescriptionGenerator


class GithubClient:
    """
    A client to interact with the Github API with authentication.
    """

    def __init__(self, github_token: Optional[str] = None, access_token: Optional[str] = None):
        """
        Initialize the GithubClient with optional authentication.

        Args:
            github_token: Optional GitHub personal access token for authentication.
                         If not provided, will try to get from GITHUB_TOKEN env var.
            access_token: Optional OAuth access token (takes precedence over github_token)
        """
        # Prioritize OAuth access token over personal access token
        self.token = access_token or github_token or os.getenv("GITHUB_TOKEN")
        self.logger = logging.getLogger(__name__)

        if not self.token:
            self.logger.warning("No GitHub token provided. Public repositories will work with rate limits. Private repositories will require authentication.")
            self.github = Github()
        else:
            if access_token:
                self.logger.info("Using OAuth access token for GitHub authentication")
            else:
                self.logger.info("Using personal access token for GitHub authentication")
            self.github = Github(self.token)

    def clone_repository(self, repository: str, target_dir: str = "temp_clone") -> str:
        """
        Clone a repository by name/URL, automatically fetching the clone URL.

        Args:
            repository: Repository name in 'owner/repo' format or full GitHub URL
            target_dir: The target folder (defaults to "temp_clone")

        Returns:
            The absolute path of the cloned folder

        Raises:
            GithubException: If repository is not found or authentication fails
        """
        try:
            repo = self.github.get_repo(repository)
            clone_url = repo.clone_url

            # Add authentication to clone URL if token is available
            if self.token:
                clone_url = clone_url.replace('https://', f'https://{self.token}@')

            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)

            Repo.clone_from(clone_url, target_dir)
            self.logger.debug(f"Successfully cloned repository {repository} to {target_dir}")

            return os.path.abspath(target_dir)

        except GithubException as e:
            self.logger.error(f"Failed to fetch repository {repository}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to clone repository: {str(e)}")
            raise

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
            self.logger.debug(f"Created and checked out branch: {branch_name}")

            # Write the changed files
            for filename, content in file_changes.items():
                file_path = os.path.join(repo_path, filename)

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.logger.debug(f"Updated file: {filename}")

            # Stage all changes
            repo.git.add(A=True)

            # Commit changes
            repo.index.commit("Instrumented with Datadog")
        except Exception as e:
            self.logger.error(f"Git operation failed: {str(e)}")
            raise

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
            self.logger.debug(f"Pushed branch {branch_name} to origin")

        except Exception as e:
            self.logger.error(f"Failed to push branch: {str(e)}")
            raise

    def _create_pull_request(
        self,
        repo_owner: str,
        repo_name: str,
        branch_name: str,
        pr_description: PRDescription,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
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
            if not self.token:
                raise Exception("GitHub token required for creating pull requests")

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

            self.logger.debug(f"Created pull request: {pr.html_url}")

            return {
                "pr_url": pr.html_url,
                "pr_number": pr.number,
                "title": pr_description.title,
                "branch": branch_name,
                "status": "created",
            }

        except Exception as e:
            self.logger.error(f"Failed to create pull request: {str(e)}")
            raise

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
            raise

    def generate_pull_request(
        self,
        repo_path: str,
        repo_owner: str,
        repo_name: str,
        instrumentation_result: InstrumentationResult,
        pr_generator: PRDescriptionGenerator,
        branch_name: Optional[str] = None,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
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
                branch_name = f"feature/dd-instrument-{timestamp}"

            # Extract file changes from instrumentation result
            file_changes = instrumentation_result.file_changes

            # Create branch and commit changes first
            self.logger.debug(f"Creating branch {branch_name} and committing changes...")
            self._create_branch_and_commit(
                repo_path, branch_name, file_changes
            )

            # Get git diff for better context
            self.logger.debug("Getting git diff for PR description generation...")
            git_diff = self._get_git_diff(repo_path, base_branch)

            # Generate PR description using the actual diff
            self.logger.debug("Generating PR description from git diff...")
            pr_description = pr_generator.generate_description_from_diff(
                git_diff, list(file_changes.keys())
            )

            # Push branch to remote
            self.logger.debug("Pushing branch to remote...")
            self._push_branch(repo_path, branch_name)

            # Create pull request
            self.logger.debug("Creating pull request...")
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
            raise
