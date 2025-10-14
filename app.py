"""Streamlit dashboard for Overleaf thesis progress tracking."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.metrics import MetricsCalculator
from src.overleaf_sync import OverleafSync
from src.scheduler import MetricsScheduler
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
    calculator = MetricsCalculator()
    storage = MetricsStorage()

    scheduler = MetricsScheduler(config, sync, calculator, storage)

    # Start scheduler
    scheduler.start()

    return config, sync, calculator, storage, scheduler


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


def sidebar_add_project(config: Config, scheduler: MetricsScheduler):
    """Sidebar section for adding new projects.

    Args:
        config: Configuration instance
        scheduler: Scheduler instance
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
                    # Trigger immediate update
                    scheduler.trigger_immediate_update()
                    st.info("Triggering initial data collection...")
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


def sidebar_settings(config: Config, scheduler: MetricsScheduler):
    """Sidebar section for settings.

    Args:
        config: Configuration instance
        scheduler: Scheduler instance
    """
    st.sidebar.header("Settings")

    current_interval = config.get_update_interval()

    new_interval = st.sidebar.slider(
        "Update Interval (minutes)",
        min_value=5,
        max_value=360,
        value=current_interval,
        step=5,
        help="How often to check for updates"
    )

    if new_interval != current_interval:
        config.set_update_interval(new_interval)
        st.sidebar.success("Settings saved! Restart app to apply.")

    # Manual update button
    if st.sidebar.button("Update Now", type="primary"):
        scheduler.trigger_immediate_update()
        st.sidebar.info("Update triggered! Refresh in a moment to see results.")


def main():
    """Main application."""
    st.title("📚 Thesis Writing Progress Tracker")
    st.markdown("Track your Overleaf thesis progress with automated word and page counts")

    # Initialize components
    config, sync, calculator, storage, scheduler = initialize_components()

    # Sidebar
    sidebar_add_project(config, scheduler)
    st.sidebar.divider()
    sidebar_remove_project(config, storage, sync)
    st.sidebar.divider()
    sidebar_settings(config, scheduler)

    # Display scheduler status
    status = scheduler.get_status()
    st.sidebar.divider()
    st.sidebar.caption(f"Scheduler: {'🟢 Running' if status['is_running'] else '🔴 Stopped'}")
    if status['last_update_time']:
        st.sidebar.caption(f"Last update: {status['last_update_time'].strftime('%H:%M:%S')}")

    # Main content
    projects = config.get_projects()

    if not projects:
        st.info("👈 Add your first project using the sidebar to start tracking progress!")
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

        # Show recent updates
        st.divider()
        st.header("Recent Updates")

        if status['update_status']:
            update_data = []
            for proj_id, proj_status in status['update_status'].items():
                update_data.append({
                    'Project': proj_status['project_name'],
                    'Time': proj_status['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'Words': proj_status['word_count'] or 'N/A',
                    'Pages': proj_status['page_count'] or 'N/A',
                    'Status': '✅' if proj_status['success'] else '❌',
                    'Message': proj_status['message']
                })

            df = pd.DataFrame(update_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No updates yet. Wait for the first scheduled update or click 'Update Now'.")


if __name__ == "__main__":
    main()
