"""Data storage module using SQLite."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd


logger = logging.getLogger(__name__)


class MetricsStorage:
    """Manages storage of metrics in SQLite database."""

    def __init__(self, db_path: str = "data/metrics.db"):
        """Initialize metrics storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                word_count INTEGER,
                page_count INTEGER,
                commit_hash TEXT
            )
        """)

        # Create index on project_id and timestamp for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_timestamp
            ON metrics (project_id, timestamp)
        """)

        conn.commit()
        conn.close()
        logger.info("Database initialized")

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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO metrics (project_id, timestamp, word_count, page_count, commit_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, timestamp.isoformat(), word_count, page_count, commit_hash)
            )

            conn.commit()
            conn.close()

            logger.info(
                f"Saved metrics for {project_id}: "
                f"words={word_count}, pages={page_count}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save metrics: {str(e)}")
            return False

    def get_latest_metrics(self, project_id: str) -> Optional[Tuple[datetime, int, int]]:
        """Get the latest metrics for a project.

        Args:
            project_id: Project ID

        Returns:
            Tuple of (timestamp, word_count, page_count) or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT timestamp, word_count, page_count
                FROM metrics
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (project_id,)
            )

            row = cursor.fetchone()
            conn.close()

            if row:
                timestamp = datetime.fromisoformat(row[0])
                return timestamp, row[1], row[2]
            return None

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
            conn = sqlite3.connect(self.db_path)

            query = """
                SELECT timestamp, word_count, page_count, commit_hash
                FROM metrics
                WHERE project_id = ?
            """
            params = [project_id]

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            query += " ORDER BY timestamp ASC"

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)

            return df

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
            conn = sqlite3.connect(self.db_path)

            query = "SELECT project_id, timestamp, word_count, page_count FROM metrics WHERE 1=1"
            params = []

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            query += " ORDER BY timestamp ASC"

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])

            return df

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

        # Calculate deltas
        word_count_delta = 0
        page_count_delta = 0

        if len(df) > 1:
            previous = df.iloc[-2]
            if latest['word_count'] and previous['word_count']:
                word_count_delta = latest['word_count'] - previous['word_count']
            if latest['page_count'] and previous['page_count']:
                page_count_delta = latest['page_count'] - previous['page_count']

        return {
            'current_word_count': int(latest['word_count']) if latest['word_count'] else 0,
            'current_page_count': int(latest['page_count']) if latest['page_count'] else 0,
            'word_count_delta': word_count_delta,
            'page_count_delta': page_count_delta,
            'last_update': latest.name,
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM metrics WHERE project_id = ?", (project_id,))

            conn.commit()
            conn.close()

            logger.info(f"Deleted all metrics for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete project data: {str(e)}")
            return False
