"""Overleaf Git synchronization module."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import git
from git import Repo


logger = logging.getLogger(__name__)


class OverleafSync:
    """Handles synchronization with Overleaf Git repositories."""

    def __init__(self, projects_dir: str = "data/projects", token: str = ""):
        """Initialize Overleaf sync manager.

        Args:
            projects_dir: Directory to store cloned projects
            token: Overleaf authentication token
        """
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.token = token

    def _get_auth_url(self, git_url: str) -> str:
        """Construct authenticated Git URL.

        Args:
            git_url: Base Git URL

        Returns:
            Authenticated Git URL with embedded token
        """
        if not self.token:
            logger.warning("No Overleaf token provided")
            return git_url

        # Replace https:// with https://git:TOKEN@
        if git_url.startswith("https://"):
            return git_url.replace("https://", f"https://git:{self.token}@")
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
        """Clone an Overleaf project.

        Args:
            project_id: Project ID
            git_url: Git repository URL

        Returns:
            Tuple of (success, message)
        """
        project_path = self._get_project_path(project_id)

        if project_path.exists():
            return False, f"Project already exists at {project_path}"

        try:
            auth_url = self._get_auth_url(git_url)
            logger.info(f"Cloning project {project_id}...")

            # Clone the repository
            Repo.clone_from(auth_url, project_path)
            logger.info(f"Successfully cloned project {project_id}")
            return True, "Project cloned successfully"

        except git.exc.GitCommandError as e:
            error_msg = f"Failed to clone project: {str(e)}"
            logger.error(error_msg)
            # Clean up partial clone if it exists
            if project_path.exists():
                import shutil
                shutil.rmtree(project_path)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error cloning project: {str(e)}"
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
