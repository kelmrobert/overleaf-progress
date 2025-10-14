"""Configuration management for Overleaf Progress Tracker."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class Config:
    """Manages application configuration and project list."""

    def __init__(self, config_path: str = "data/config.json"):
        """Initialize configuration manager.

        Args:
            config_path: Path to the configuration JSON file
        """
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                "projects": [],
                "update_interval_minutes": 60,
                "overleaf_token": os.getenv("OVERLEAF_TOKEN", "")
            }
            self._save_config()

    def _save_config(self) -> None:
        """Save configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_projects(self) -> List[Dict[str, str]]:
        """Get list of tracked projects.

        Returns:
            List of project dictionaries with id, name, and git_url
        """
        return self.data.get("projects", [])

    def add_project(self, project_id: str, name: str, git_url: Optional[str] = None) -> bool:
        """Add a new project to track.

        Args:
            project_id: Overleaf project ID
            name: Display name for the project
            git_url: Optional custom git URL (will be constructed if not provided)

        Returns:
            True if project was added, False if it already exists
        """
        # Check if project already exists
        for project in self.data["projects"]:
            if project["id"] == project_id:
                return False

        # Construct git URL if not provided
        if git_url is None:
            git_url = f"https://git.overleaf.com/{project_id}"

        project = {
            "id": project_id,
            "name": name,
            "git_url": git_url
        }

        self.data["projects"].append(project)
        self._save_config()
        return True

    def remove_project(self, project_id: str) -> bool:
        """Remove a project from tracking.

        Args:
            project_id: Overleaf project ID to remove

        Returns:
            True if project was removed, False if not found
        """
        initial_length = len(self.data["projects"])
        self.data["projects"] = [
            p for p in self.data["projects"] if p["id"] != project_id
        ]

        if len(self.data["projects"]) < initial_length:
            self._save_config()
            return True
        return False

    def get_overleaf_token(self) -> str:
        """Get Overleaf authentication token.

        Returns:
            Overleaf token from config or environment variable
        """
        # Prefer environment variable over config file
        token = os.getenv("OVERLEAF_TOKEN")
        if token:
            return token
        return self.data.get("overleaf_token", "")

    def set_overleaf_token(self, token: str) -> None:
        """Set Overleaf authentication token.

        Args:
            token: Overleaf authentication token
        """
        self.data["overleaf_token"] = token
        self._save_config()

    def get_update_interval(self) -> int:
        """Get update interval in minutes.

        Returns:
            Update interval in minutes
        """
        return self.data.get("update_interval_minutes", 60)

    def set_update_interval(self, minutes: int) -> None:
        """Set update interval in minutes.

        Args:
            minutes: Update interval in minutes
        """
        self.data["update_interval_minutes"] = minutes
        self._save_config()
