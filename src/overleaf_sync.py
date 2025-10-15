"""Overleaf Git synchronization module."""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import git
from git import Repo


logger = logging.getLogger(__name__)


class OverleafSync:
    """Handles synchronization with Overleaf Git repositories."""

    def __init__(self, projects_dir: str = "data/projects", tokens: Optional[List[str]] = None):
        """Initialize Overleaf sync manager.

        Args:
            projects_dir: Directory to store cloned projects
            tokens: List of Overleaf authentication tokens (will try each in order)
        """
        self.projects_dir = Path(projects_dir).resolve()
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.tokens = tokens or []

    def _get_auth_url(self, git_url: str, token: str) -> str:
        """Construct authenticated Git URL.

        Args:
            git_url: Base Git URL
            token: Authentication token

        Returns:
            Authenticated Git URL with embedded token
        """
        if not token:
            logger.warning("No Overleaf token provided")
            return git_url

        # Replace https:// with https://git:TOKEN@
        if git_url.startswith("https://"):
            return git_url.replace("https://", f"https://git:{token}@")
        return git_url

    def _get_project_path(self, project_id: str) -> Path:
        """Get local path for a project.

        Args:
            project_id: Project ID

        Returns:
            Path to local project directory
        """
        return self.projects_dir / project_id

    def clone_project(self, project_id: str, git_url: str) -> Tuple[bool, str]:
        """Clone an Overleaf project, trying each token until one works.

        Args:
            project_id: Project ID
            git_url: Git repository URL

        Returns:
            Tuple of (success, message)
        """
        project_path = self._get_project_path(project_id)

        if project_path.exists():
            return False, f"Project already exists at {project_path}"

        if not self.tokens:
            return False, "No authentication tokens provided"

        # Try each token
        last_error = ""
        for i, token in enumerate(self.tokens):
            try:
                auth_url = self._get_auth_url(git_url, token)
                logger.info(f"Cloning project {project_id} with token {i+1}/{len(self.tokens)}...")

                # Clone the repository
                Repo.clone_from(auth_url, project_path)
                logger.info(f"Successfully cloned project {project_id} with token {i+1}")
                return True, f"Project cloned successfully with token {i+1}"

            except git.exc.GitCommandError as e:
                last_error = f"Failed with token {i+1}: {str(e)}"
                logger.warning(last_error)
                # Clean up partial clone if it exists
                if project_path.exists():
                    import shutil
                    shutil.rmtree(project_path)
                # Continue to next token

            except Exception as e:
                last_error = f"Unexpected error with token {i+1}: {str(e)}"
                logger.warning(last_error)
                # Continue to next token

        # All tokens failed
        error_msg = f"Failed to clone with all {len(self.tokens)} tokens. Last error: {last_error}"
        logger.error(error_msg)
        return False, error_msg

    def pull_updates(self, project_id: str) -> Tuple[bool, str, bool]:
        """Pull latest updates for a project.

        Args:
            project_id: Project ID

        Returns:
            Tuple of (success, message, has_changes)
        """
        project_path = self._get_project_path(project_id)

        if not project_path.exists():
            return False, "Project not found locally. Please clone it first.", False

        try:
            # Configure git to trust this directory (fixes ownership issues in containers)
            subprocess.run(
                ["git", "config", "--global", "--add", "safe.directory", str(project_path)],
                check=False,  # Don't fail if already exists
                capture_output=True
            )

            repo = Repo(project_path)

            # Get current commit hash
            old_commit = repo.head.commit.hexsha

            # Pull updates
            origin = repo.remotes.origin
            pull_info = origin.pull()

            # Get new commit hash
            new_commit = repo.head.commit.hexsha

            # Check if there were changes
            has_changes = old_commit != new_commit

            if has_changes:
                logger.info(f"Project {project_id} updated: {old_commit[:7]} -> {new_commit[:7]}")
                return True, f"Updated successfully ({new_commit[:7]})", True
            else:
                logger.info(f"Project {project_id} already up to date")
                return True, "Already up to date", False

        except git.exc.GitCommandError as e:
            error_msg = f"Failed to pull updates: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, False
        except Exception as e:
            error_msg = f"Unexpected error pulling updates: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, False

    def get_latest_commit_hash(self, project_id: str) -> Optional[str]:
        """Get the latest commit hash for a project.

        Args:
            project_id: Project ID

        Returns:
            Commit hash or None if not available
        """
        project_path = self._get_project_path(project_id)

        if not project_path.exists():
            return None

        try:
            # Configure git to trust this directory (fixes ownership issues in containers)
            subprocess.run(
                ["git", "config", "--global", "--add", "safe.directory", str(project_path)],
                check=False,  # Don't fail if already exists
                capture_output=True
            )

            repo = Repo(project_path)
            return repo.head.commit.hexsha
        except Exception as e:
            logger.error(f"Failed to get commit hash: {str(e)}")
            return None

    def get_project_path(self, project_id: str) -> Optional[Path]:
        """Get the local path for a project if it exists.

        Args:
            project_id: Project ID

        Returns:
            Path to project directory or None if not found
        """
        project_path = self._get_project_path(project_id)
        if project_path.exists():
            return project_path
        return None

    def remove_project(self, project_id: str) -> Tuple[bool, str]:
        """Remove a project's local clone.

        Args:
            project_id: Project ID

        Returns:
            Tuple of (success, message)
        """
        project_path = self._get_project_path(project_id)

        if not project_path.exists():
            return False, "Project not found"

        try:
            import shutil
            shutil.rmtree(project_path)
            logger.info(f"Removed project {project_id}")
            return True, "Project removed successfully"
        except Exception as e:
            error_msg = f"Failed to remove project: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
