"""Streamlit dashboard for Overleaf thesis progress tracking."""

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
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
    initial_sidebar_state="expanded"
)


@st.cache_resource
def initialize_components():
    """Initialize application components."""
    config = Config()
    token = config.get_overleaf_token()
    sync = OverleafSync(token=token)
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

    fig = go.Figure()

    for project in projects:
        project_id = project['id']
        project_name = project['name']

        df = storage.get_metrics_history(project_id)

        if not df.empty and metric_type in df.columns:
            # Filter out None values
            df_filtered = df[df[metric_type].notna()]

            if not df_filtered.empty:
                fig.add_trace(go.Scatter(
                    x=df_filtered.index,
                    y=df_filtered[metric_type],
                    mode='lines+markers',
                    name=project_name,
                    hovertemplate=f'<b>{project_name}</b><br>' +
                                  'Date: %{x}<br>' +
                                  f'{metric_type.replace("_", " ").title()}: %{y}<br>' +
                                  '<extra></extra>'
                ))

    # Update layout
    title = "Word Count Progress" if metric_type == "word_count" else "Page Count Progress"
    y_label = "Words" if metric_type == "word_count" else "Pages"

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        hovermode='x unified',
        height=500,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)


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
            help="A friendly name for this project (e.g., 'Alice's Thesis')"
        )
        git_url = st.text_input(
            "Git URL (optional)",
            help="Leave empty to auto-generate from project ID"
        )

        submitted = st.form_submit_button("Add Project")

        if submitted:
            if not project_id or not project_name:
                st.error("Please provide both Project ID and Display Name")
            else:
                # Add project to config
                url = git_url if git_url else None
                success = config.add_project(project_id, project_name, url)

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

    st.sidebar.info(
        "Metrics are extracted hourly by a cron job. "
        "Check `data/extraction.log` for details."
    )

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

    update_interval = config.get_update_interval()
    st.sidebar.caption(f"Update interval: {update_interval} minutes")


def main():
    """Main application."""
    st.title("📚 Thesis Writing Progress Tracker")
    st.markdown("Track your Overleaf thesis progress with automated word and page counts")

    # Initialize components
    config, sync, storage = initialize_components()

    # Sidebar
    sidebar_add_project(config, sync)
    st.sidebar.divider()
    sidebar_remove_project(config, storage, sync)
    st.sidebar.divider()
    sidebar_info(config, storage)

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

        tab1, tab2 = st.tabs(["Word Count", "Page Count"])

        with tab1:
            plot_metrics_over_time(storage, projects, "word_count")

        with tab2:
            plot_metrics_over_time(storage, projects, "page_count")


if __name__ == "__main__":
    main()
