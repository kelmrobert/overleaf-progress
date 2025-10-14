"""Background scheduler for automated metric updates."""

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import Config
from src.metrics import MetricsCalculator
from src.overleaf_sync import OverleafSync
from src.storage import MetricsStorage


logger = logging.getLogger(__name__)


class MetricsScheduler:
    """Manages scheduled updates of project metrics."""

    def __init__(
        self,
        config: Config,
        sync: OverleafSync,
        calculator: MetricsCalculator,
        storage: MetricsStorage
    ):
        """Initialize metrics scheduler.

        Args:
            config: Configuration manager
            sync: Overleaf sync manager
            calculator: Metrics calculator
            storage: Metrics storage
        """
        self.config = config
        self.sync = sync
        self.calculator = calculator
        self.storage = storage
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.last_update_time: Optional[datetime] = None
        self.update_status: dict = {}
        self._lock = threading.Lock()

    def update_project_metrics(self, project_id: str, project_name: str, git_url: str) -> dict:
        """Update metrics for a single project.

        Args:
            project_id: Project ID
            project_name: Project display name
            git_url: Git repository URL

        Returns:
            Dictionary with update status
        """
        logger.info(f"Updating metrics for project: {project_name} ({project_id})")

        status = {
            'project_id': project_id,
            'project_name': project_name,
            'timestamp': datetime.now(),
            'success': False,
            'message': '',
            'word_count': None,
            'page_count': None
        }

        try:
            # Check if project exists locally
            project_path = self.sync.get_project_path(project_id)

            if project_path is None:
                # Clone the project
                logger.info(f"Cloning project {project_id}...")
                success, msg = self.sync.clone_project(project_id, git_url)
                if not success:
                    status['message'] = f"Failed to clone: {msg}"
                    return status
                project_path = self.sync.get_project_path(project_id)

            # Pull latest changes
            logger.info(f"Pulling updates for {project_id}...")
            success, msg, has_changes = self.sync.pull_updates(project_id)

            if not success:
                status['message'] = f"Failed to pull: {msg}"
                return status

            # Get current commit hash
            commit_hash = self.sync.get_latest_commit_hash(project_id)

            # Calculate metrics
            logger.info(f"Calculating metrics for {project_id}...")
            word_count, page_count, metrics_msg = self.calculator.calculate_metrics(project_path)

            # Save metrics
            self.storage.save_metric(
                project_id=project_id,
                word_count=word_count,
                page_count=page_count,
                commit_hash=commit_hash
            )

            status['success'] = True
            status['word_count'] = word_count
            status['page_count'] = page_count
            status['message'] = f"{metrics_msg} | {msg}"

            logger.info(f"Successfully updated {project_name}: {metrics_msg}")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Error updating {project_name}: {error_msg}")
            status['message'] = error_msg

        return status

    def update_all_projects(self) -> None:
        """Update metrics for all configured projects."""
        logger.info("Starting scheduled update for all projects...")

        with self._lock:
            self.last_update_time = datetime.now()
            self.update_status.clear()

        projects = self.config.get_projects()

        if not projects:
            logger.warning("No projects configured for tracking")
            return

        for project in projects:
            project_id = project['id']
            project_name = project['name']
            git_url = project['git_url']

            status = self.update_project_metrics(project_id, project_name, git_url)

            with self._lock:
                self.update_status[project_id] = status

        logger.info("Completed scheduled update for all projects")

    def start(self, interval_minutes: Optional[int] = None) -> None:
        """Start the scheduler.

        Args:
            interval_minutes: Update interval in minutes (uses config if not provided)
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        if interval_minutes is None:
            interval_minutes = self.config.get_update_interval()

        logger.info(f"Starting scheduler with {interval_minutes} minute interval")

        # Add job to scheduler
        self.scheduler.add_job(
            self.update_all_projects,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='update_metrics',
            name='Update project metrics',
            replace_existing=True
        )

        # Start the scheduler
        self.scheduler.start()
        self.is_running = True

        # Run an immediate update
        logger.info("Running immediate update on scheduler start...")
        threading.Thread(target=self.update_all_projects, daemon=True).start()

    def stop(self) -> None:
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        logger.info("Stopping scheduler")
        self.scheduler.shutdown()
        self.is_running = False

    def get_status(self) -> dict:
        """Get current scheduler status.

        Returns:
            Dictionary with scheduler status
        """
        with self._lock:
            return {
                'is_running': self.is_running,
                'last_update_time': self.last_update_time,
                'update_status': dict(self.update_status),
                'next_run_time': self.scheduler.get_jobs()[0].next_run_time if self.scheduler.get_jobs() else None
            }

    def trigger_immediate_update(self) -> None:
        """Trigger an immediate update outside of the schedule."""
        logger.info("Triggering immediate update...")
        threading.Thread(target=self.update_all_projects, daemon=True).start()
