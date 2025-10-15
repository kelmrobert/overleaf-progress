"""Data storage module using JSON files."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from src.dataframe import group_and_pivot_metrics


logger = logging.getLogger(__name__)


class MetricsStorage:
    """Manages storage of metrics in JSON files."""

    def __init__(self, data_dir: str = "data"):
        """Initialize metrics storage.

        Args:
            data_dir: Directory to store JSON files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.data_dir / "metrics.json"
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensure the metrics file exists."""
        if not self.metrics_file.exists():
            self._save_data([])
            logger.info("Created new metrics file")

    def _load_data(self) -> List[dict]:
        """Load all metrics from JSON file.

        Returns:
            List of metric dictionaries
        """
        try:
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metrics: {str(e)}")
            return []

    def _save_data(self, data: List[dict]) -> None:
        """Save all metrics to JSON file.

        Args:
            data: List of metric dictionaries
        """
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save metrics: {str(e)}")

    def save_metric(
        self,
        project_id: str,
        word_count: Optional[int],
        page_count: Optional[int],
        commit_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """Save a metric entry.

        Args:
            project_id: Project ID
            word_count: Word count (can be None if calculation failed)
            page_count: Page count (can be None if calculation failed)
            commit_hash: Optional Git commit hash
            timestamp: Optional timestamp (defaults to now)

        Returns:
            True if successful
        """
        if timestamp is None:
            timestamp = datetime.now()

        try:
            data = self._load_data()

            metric = {
                'project_id': project_id,
                'timestamp': timestamp.isoformat(),
                'word_count': word_count,
                'page_count': page_count,
                'commit_hash': commit_hash
            }

            data.append(metric)
            self._save_data(data)

            logger.info(
                f"Saved metrics for {project_id}: "
                f"words={word_count}, pages={page_count}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save metrics: {str(e)}")
            return False

    def get_latest_metrics(self, project_id: str) -> Optional[dict]:
        """Get the latest metrics for a project.

        Args:
            project_id: Project ID

        Returns:
            Dictionary with timestamp, word_count, page_count or None
        """
        try:
            data = self._load_data()

            # Filter by project_id and sort by timestamp
            project_data = [m for m in data if m['project_id'] == project_id]
            if not project_data:
                return None

            # Sort by timestamp descending
            project_data.sort(key=lambda x: x['timestamp'], reverse=True)
            latest = project_data[0]

            return {
                'timestamp': datetime.fromisoformat(latest['timestamp']),
                'word_count': latest['word_count'],
                'page_count': latest['page_count']
            }

        except Exception as e:
            logger.error(f"Failed to get latest metrics: {str(e)}")
            return None

    def get_metrics_history(
        self,
        project_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Get metrics history for a project.

        Args:
            project_id: Project ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with columns: timestamp, word_count, page_count
        """
        try:
            data = self._load_data()

            # Filter by project_id
            project_data = [m for m in data if m['project_id'] == project_id]

            if not project_data:
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(project_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Apply date filters
            if start_date:
                df = df[df['timestamp'] >= start_date]
            if end_date:
                df = df[df['timestamp'] <= end_date]

            # Set timestamp as index and sort
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)

            return df[['word_count', 'page_count', 'commit_hash']]

        except Exception as e:
            logger.error(f"Failed to get metrics history: {str(e)}")
            return pd.DataFrame()

    def get_all_metrics_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Get metrics history for all projects.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with columns: project_id, timestamp, word_count, page_count
        """
        try:
            data = self._load_data()

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Apply date filters
            if start_date:
                df = df[df['timestamp'] >= start_date]
            if end_date:
                df = df[df['timestamp'] <= end_date]

            df.sort_values('timestamp', inplace=True)

            return df[['project_id', 'timestamp', 'word_count', 'page_count']]

        except Exception as e:
            logger.error(f"Failed to get all metrics history: {str(e)}")
            return pd.DataFrame()

    def get_project_summary(self, project_id: str) -> Optional[dict]:
        """Get summary statistics for a project.

        Args:
            project_id: Project ID

        Returns:
            Dictionary with summary statistics or None
        """
        df = self.get_metrics_history(project_id)

        if df.empty:
            return None

        # Get latest metrics
        latest = df.iloc[-1]

        # Calculate deltas comparing today vs yesterday (last different day)
        word_count_delta = 0
        page_count_delta = 0

        if len(df) > 1:
            # Convert index to date only (remove time component)
            df_copy = df.copy()
            df_copy['date'] = df_copy.index.date

            # Get today's date
            today = df_copy.index[-1].date()

            # Find yesterday's data (last date before today)
            df_yesterday = df_copy[df_copy['date'] < today]

            if not df_yesterday.empty:
                # Get the last entry from yesterday
                yesterday_latest = df_yesterday.iloc[-1]

                if pd.notna(latest['word_count']) and pd.notna(yesterday_latest['word_count']):
                    word_count_delta = int(latest['word_count'] - yesterday_latest['word_count'])
                if pd.notna(latest['page_count']) and pd.notna(yesterday_latest['page_count']):
                    page_count_delta = int(latest['page_count'] - yesterday_latest['page_count'])

        return {
            'current_word_count': int(latest['word_count']) if pd.notna(latest['word_count']) else 0,
            'current_page_count': int(latest['page_count']) if pd.notna(latest['page_count']) else 0,
            'word_count_delta': word_count_delta,
            'page_count_delta': page_count_delta,
            'last_update': df.index[-1],
            'total_measurements': len(df)
        }

    def delete_project_data(self, project_id: str) -> bool:
        """Delete all metrics for a project.

        Args:
            project_id: Project ID

        Returns:
            True if successful
        """
        try:
            data = self._load_data()

            # Filter out the project
            filtered_data = [m for m in data if m['project_id'] != project_id]

            self._save_data(filtered_data)

            logger.info(f"Deleted all metrics for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete project data: {str(e)}")
            return False

    def get_processed_metrics(self, project_names: dict, metric_type: str) -> pd.DataFrame:
        """Get processed and pivoted metrics for all projects.

        Args:
            project_names: Dictionary mapping project IDs to names.
            metric_type: The metric to use (e.g., 'word_count').

        Returns:
            A processed DataFrame ready for charting.
        """
        all_metrics_df = self.get_all_metrics_history()
        if all_metrics_df.empty:
            return pd.DataFrame()

        return group_and_pivot_metrics(all_metrics_df, project_names, metric_type)
