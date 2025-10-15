#!/usr/bin/env python3
"""Standalone script to extract metrics from Overleaf projects.

This script is intended to be run via cron hourly.
It reads the project configuration, syncs with Overleaf,
calculates metrics, and stores them in JSON format.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.metrics import MetricsCalculator
from src.overleaf_sync import OverleafSync
from src.storage import MetricsStorage


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/extraction.log')
    ]
)
logger = logging.getLogger(__name__)


def extract_project_metrics(
    project_id: str,
    project_name: str,
    git_url: str,
    sync: OverleafSync,
    calculator: MetricsCalculator,
    storage: MetricsStorage
) -> bool:
    """Extract metrics for a single project.

    Args:
        project_id: Project ID
        project_name: Project display name
        git_url: Git repository URL
        sync: Overleaf sync manager
        calculator: Metrics calculator
        storage: Metrics storage

    Returns:
        True if successful
    """
    logger.info(f"Processing project: {project_name} ({project_id})")

    try:
        # Check if project exists locally
        project_path = sync.get_project_path(project_id)

        if project_path is None:
            # Clone the project
            logger.info(f"Cloning project {project_id}...")
            success, msg = sync.clone_project(project_id, git_url)
            if not success:
                logger.error(f"Failed to clone {project_name}: {msg}")
                return False
            project_path = sync.get_project_path(project_id)

        # Pull latest changes
        logger.info(f"Pulling updates for {project_id}...")
        success, msg, has_changes = sync.pull_updates(project_id)

        if not success:
            logger.error(f"Failed to pull {project_name}: {msg}")
            return False

        if has_changes:
            logger.info(f"New changes detected for {project_name}")
        else:
            logger.info(f"No new changes for {project_name}")

        # Get current commit hash
        commit_hash = sync.get_latest_commit_hash(project_id)

        # Calculate metrics
        logger.info(f"Calculating metrics for {project_id}...")
        word_count, page_count, metrics_msg = calculator.calculate_metrics(project_path)

        # Save metrics
        storage.save_metric(
            project_id=project_id,
            word_count=word_count,
            page_count=page_count,
            commit_hash=commit_hash
        )

        logger.info(f"Successfully processed {project_name}: {metrics_msg}")
        return True

    except Exception as e:
        logger.error(f"Error processing {project_name}: {str(e)}", exc_info=True)
        return False


def main():
    """Main extraction routine."""
    logger.info("=" * 60)
    logger.info("Starting metrics extraction")
    logger.info("=" * 60)

    # Initialize components
    config = Config()
    token = config.get_overleaf_token()

    if not token:
        logger.error("OVERLEAF_TOKEN not set. Please configure it.")
        sys.exit(1)

    sync = OverleafSync(token=token)
    calculator = MetricsCalculator()
    storage = MetricsStorage()

    # Get projects
    projects = config.get_projects()

    if not projects:
        logger.warning("No projects configured for tracking")
        logger.info("Add projects via the dashboard or edit data/config.json")
        sys.exit(0)

    logger.info(f"Found {len(projects)} project(s) to process")

    # Process each project
    success_count = 0
    for project in projects:
        project_id = project['id']
        project_name = project['name']
        git_url = project['git_url']

        if extract_project_metrics(
            project_id, project_name, git_url,
            sync, calculator, storage
        ):
            success_count += 1

    # Summary
    logger.info("=" * 60)
    logger.info(f"Extraction complete: {success_count}/{len(projects)} succeeded")
    logger.info("=" * 60)

    if success_count < len(projects):
        sys.exit(1)


if __name__ == "__main__":
    main()
