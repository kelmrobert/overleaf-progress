"""Streamlit dashboard for Overleaf thesis progress tracking."""

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.overleaf_sync import OverleafSync
from src.storage import MetricsStorage


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Page configuration
st.set_page_config(
    page_title="Thesis Progress Tracker",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)


@st.cache_resource
def initialize_components():
    """Initialize application components."""
    config = Config()
    tokens = config.get_overleaf_tokens()
    sync = OverleafSync(tokens=tokens)
    storage = MetricsStorage()

    return config, sync, storage


def plot_metrics_over_time(storage: MetricsStorage, projects: list, metric_type: str = "word_count"):
    """Plot metrics over time for all projects.

    Args:
        storage: Metrics storage instance
        projects: List of project dictionaries
        metric_type: Either "word_count" or "page_count"
    """
    if not projects:
        st.info("No projects added yet. Add a project to start tracking!")
        return

    project_names = {p['id']: p['name'] for p in projects}
    processed_df = storage.get_processed_metrics(project_names, metric_type)

    if not processed_df.empty:
        # Add title
        title = "Word Count Progress" if metric_type == "word_count" else "Page Count Progress"
        st.write(f"**{title}**")

        # Define colors
        colors = ["#FF0000", "#0000FF"]  # Red and Blue

        # Use Streamlit line chart with colors
        st.line_chart(processed_df, height=400, color=colors)
    else:
        st.info("No data available yet")


def plot_daily_change(storage: MetricsStorage, projects: list, metric_type: str = "word_count"):
    """Plot daily changes in metrics as bar charts grouped by date.

    Args:
        storage: Metrics storage instance
        projects: List of project dictionaries
        metric_type: Either "word_count" or "page_count"
    """
    if not projects:
        st.info("No projects added yet. Add a project to start tracking!")
        return

    project_names = {p['id']: p['name'] for p in projects}
    processed_df = storage.get_processed_metrics(project_names, metric_type)

    if not processed_df.empty:
        # Calculate daily changes
        daily_changes = processed_df.diff()

        # Resample to daily frequency, taking the last value of each day
        daily_sum = daily_changes.resample('D').sum()

        # Filter out days with no change
        daily_sum = daily_sum[(daily_sum != 0).any(axis=1)]

        if not daily_sum.empty:
            # Add title
            title = "Words Added Per Day" if metric_type == "word_count" else "Pages Added Per Day"
            st.write(f"**{title}**")

            # Define colors
            colors = ["#FF0000", "#0000FF"]  # Red and Blue

            # Use Streamlit bar chart with colors
            st.bar_chart(daily_sum, height=400, color=colors)
        else:
            st.info("No daily changes to display.")
    else:
        st.info("No data available yet")


def display_project_cards(storage: MetricsStorage, projects: list):
    """Display current metrics as cards.

    Args:
        storage: Metrics storage instance
        projects: List of project dictionaries
    """
    if not projects:
        return

    cols = st.columns(len(projects))

    for idx, project in enumerate(projects):
        project_id = project['id']
        project_name = project['name']

        summary = storage.get_project_summary(project_id)

        with cols[idx]:
            st.subheader(project_name)

            if summary:
                col1, col2 = st.columns(2)

                with col1:
                    st.metric(
                        label="Words",
                        value=f"{summary['current_word_count']:,}",
                        delta=summary['word_count_delta']
                    )

                with col2:
                    st.metric(
                        label="Pages",
                        value=summary['current_page_count'],
                        delta=summary['page_count_delta']
                    )

                st.caption(f"Last updated: {summary['last_update'].strftime('%Y-%m-%d %H:%M')}")
            else:
                st.info("No data yet")


def sidebar_add_project(config: Config, sync: OverleafSync):
    """Sidebar section for adding new projects.

    Args:
        config: Configuration instance
        sync: Sync instance
    """
    st.sidebar.header("Add New Project")

    with st.sidebar.form("add_project_form"):
        project_id = st.text_input(
            "Overleaf Project ID",
            help="Find this in your Overleaf project URL"
        )
        project_name = st.text_input(
            "Display Name",
            help="A friendly name for this project"
        )

        submitted = st.form_submit_button("Add Project")

        if submitted:
            if not project_id or not project_name:
                st.error("Please provide both Project ID and Display Name")
            else:
                # Add project to config
                success = config.add_project(project_id, project_name, None)

                if success:
                    st.success(f"Project '{project_name}' added successfully!")
                    st.info("The metrics will be collected on the next hourly run.")
                    st.rerun()
                else:
                    st.error("Project already exists")


def sidebar_remove_project(config: Config, storage: MetricsStorage, sync: OverleafSync):
    """Sidebar section for removing projects.

    Args:
        config: Configuration instance
        storage: Storage instance
        sync: Sync instance
    """
    projects = config.get_projects()

    if projects:
        st.sidebar.header("Remove Project")

        project_names = {p['name']: p['id'] for p in projects}
        selected_name = st.sidebar.selectbox(
            "Select project to remove",
            options=list(project_names.keys())
        )

        if st.sidebar.button("Remove Project", type="secondary"):
            project_id = project_names[selected_name]

            # Remove from config
            config.remove_project(project_id)

            # Remove data
            storage.delete_project_data(project_id)

            # Remove local clone
            sync.remove_project(project_id)

            st.sidebar.success(f"Removed '{selected_name}'")
            st.rerun()


def sidebar_info(config: Config, storage: MetricsStorage):
    """Sidebar section with extraction info.

    Args:
        config: Configuration instance
        storage: Storage instance
    """
    st.sidebar.header("Data Extraction")

    st.caption("Metrics are extracted hourly by, you can trigger a manual extraction below.")

    # Manual extraction button
    if st.sidebar.button("💾 Extract Manually", type="primary"):
        with st.sidebar.status("Extracting metrics...", expanded=True) as status:
            st.write("Running extraction script...")
            try:
                # Run the extraction script
                script_path = Path(__file__).parent / "extract_metrics.py"
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )

                if result.returncode == 0:
                    status.update(label="Extraction complete!", state="complete")
                    st.sidebar.success("Metrics extracted successfully!")
                    # Show some output
                    if result.stdout:
                        with st.sidebar.expander("View extraction log"):
                            st.code(result.stdout, language="text")
                    st.rerun()
                else:
                    status.update(label="Extraction failed", state="error")
                    st.sidebar.error("Extraction failed. Check logs for details.")
                    if result.stderr:
                        with st.sidebar.expander("View error log"):
                            st.code(result.stderr, language="text")
            except subprocess.TimeoutExpired:
                status.update(label="Extraction timeout", state="error")
                st.sidebar.error("Extraction timed out after 5 minutes")
            except Exception as e:
                status.update(label="Extraction error", state="error")
                st.sidebar.error(f"Error running extraction: {str(e)}")

    # Show last extraction time if available
    try:
        log_file = Path("data/extraction.log")
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1]
                    if "Starting metrics extraction" in last_line:
                        st.sidebar.caption(f"Last extraction: Check log file")
    except Exception:
        pass


def main():
    """Main application."""
    st.title("📚 Thesis Progress Tracker")
    st.markdown("Track your Overleaf thesis progress with automated word and page counts")

    # Initialize components
    config, sync, storage = initialize_components()

    # Sidebar
    sidebar_info(config, storage)
    st.sidebar.divider()
    sidebar_add_project(config, sync)
    st.sidebar.divider()
    sidebar_remove_project(config, storage, sync)

    # Main content
    projects = config.get_projects()

    if not projects:
        st.info("👈 Add your first project using the sidebar to start tracking progress!")
        st.markdown("""
        ### How it works
        1. Add your Overleaf project using the sidebar
        2. Metrics are automatically extracted every hour via cron
        3. View your progress over time in the charts below

        **Note:** Make sure the `extract_metrics.py` script is running via cron.
        """)
    else:
        # Display current metrics
        st.header("Current Status")
        display_project_cards(storage, projects)

        st.divider()

        # Display charts
        st.header("Progress Over Time")

        # Cumulative progress charts side by side
        st.subheader("Cumulative Progress")
        col1, col2 = st.columns(2)

        with col1:
            plot_metrics_over_time(storage, projects, "word_count")

        with col2:
            plot_metrics_over_time(storage, projects, "page_count")

        st.divider()

        # Daily changes side by side
        st.subheader("Daily Changes")
        col3, col4 = st.columns(2)

        with col3:
            plot_daily_change(storage, projects, "word_count")

        with col4:
            plot_daily_change(storage, projects, "page_count")


if __name__ == "__main__":
    main()
