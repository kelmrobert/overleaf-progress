"""Streamlit dashboard for Overleaf thesis progress tracking."""

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

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

# Professional color palette for charts - cohesive and distinctive
# Inspired by modern data visualization best practices
PROJECT_COLOR_PALETTE = [
    "#4A90E2",  # Soft Blue - calm, trustworthy
    "#E85D75",  # Coral Pink - warm, energetic
    "#50C878",  # Emerald Green - fresh, positive
    "#9B59B6",  # Amethyst Purple - creative, elegant
    "#F39C12",  # Amber Orange - vibrant, optimistic
    "#16A085",  # Teal - balanced, professional
    "#E74C3C",  # Soft Red - bold, passionate
    "#3498DB",  # Sky Blue - open, friendly
]


def get_project_colors(project_names: list) -> dict:
    """Get consistent colors for projects.

    Args:
        project_names: List of project names

    Returns:
        Dictionary mapping project names to colors
    """
    return {name: PROJECT_COLOR_PALETTE[i % len(PROJECT_COLOR_PALETTE)]
            for i, name in enumerate(project_names)}


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

        # Get consistent colors for projects
        color_map = get_project_colors(list(processed_df.columns))
        colors = [color_map[col] for col in processed_df.columns]

        # Use Streamlit line chart with colors
        st.line_chart(processed_df, height=400, color=colors)
    else:
        st.info("No data available yet")


def plot_daily_change(storage: MetricsStorage, projects: list, metric_type: str = "word_count"):
    """Plot daily changes in metrics as grouped bar charts by date.

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

            # Reshape data for grouped bars: stack by date and project
            # Convert from wide format (columns=projects) to long format
            daily_sum_reset = daily_sum.reset_index()
            date_col = daily_sum_reset.columns[0]  # Get the actual name of the date column
            melted = daily_sum_reset.melt(id_vars=date_col, var_name='Project', value_name='Change')

            # Create a date string column for display
            melted['Date'] = melted[date_col].dt.strftime('%Y-%m-%d')

            # Get consistent colors for projects
            project_list = daily_sum.columns.tolist()
            color_map = get_project_colors(project_list)

            # Create Altair grouped bar chart
            chart = alt.Chart(melted).mark_bar().encode(
                x=alt.X('Date:N', title='Date', axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('Change:Q', title=title),
                color=alt.Color('Project:N',
                                scale=alt.Scale(domain=list(color_map.keys()),
                                              range=list(color_map.values())),
                                legend=alt.Legend(title='Project')),
                xOffset='Project:N'  # This creates the grouped effect
            ).properties(
                height=400
            )

            st.altair_chart(chart, width='stretch')
        else:
            st.info("No daily changes to display.")
    else:
        st.info("No data available yet")


def plot_writing_velocity(storage: MetricsStorage, projects: list, metric_type: str = "word_count"):
    """Plot writing velocity with moving averages.

    Args:
        storage: Metrics storage instance
        projects: List of project dictionaries
        metric_type: Either "word_count" or "page_count"
    """
    if not projects:
        return

    project_names = {p['id']: p['name'] for p in projects}
    processed_df = storage.get_processed_metrics(project_names, metric_type)

    if not processed_df.empty:
        # Calculate daily changes
        daily_changes = processed_df.diff()

        # Resample to daily frequency
        daily_sum = daily_changes.resample('D').sum()

        # Calculate 7-day and 30-day moving averages
        ma_7 = daily_sum.rolling(window=7, min_periods=1).mean()
        ma_30 = daily_sum.rolling(window=30, min_periods=1).mean()

        if not daily_sum.empty:
            title = "Writing Velocity (Words/Day)" if metric_type == "word_count" else "Writing Velocity (Pages/Day)"
            st.write(f"**{title}**")

            # Combine all data for visualization
            combined_data = []

            for project in daily_sum.columns:
                # Add actual daily changes
                df_actual = daily_sum[[project]].reset_index()
                df_actual.columns = ['date', 'value']
                df_actual['Project'] = project
                df_actual['Type'] = 'Daily'
                combined_data.append(df_actual)

                # Add 7-day MA
                df_ma7 = ma_7[[project]].reset_index()
                df_ma7.columns = ['date', 'value']
                df_ma7['Project'] = project
                df_ma7['Type'] = '7-day avg'
                combined_data.append(df_ma7)

                # Add 30-day MA
                df_ma30 = ma_30[[project]].reset_index()
                df_ma30.columns = ['date', 'value']
                df_ma30['Project'] = project
                df_ma30['Type'] = '30-day avg'
                combined_data.append(df_ma30)

            melted = pd.concat(combined_data, ignore_index=True)
            melted['date'] = pd.to_datetime(melted['date'])

            # Get consistent colors for projects
            project_list = list(daily_sum.columns)
            color_map = get_project_colors(project_list)

            # Create layered chart
            base = alt.Chart(melted).encode(
                x=alt.X('date:T', title='Date')
            )

            # Daily changes as bars
            bars = base.transform_filter(
                alt.datum.Type == 'Daily'
            ).mark_bar(opacity=0.3).encode(
                y=alt.Y('value:Q', title=title),
                color=alt.Color('Project:N',
                              scale=alt.Scale(domain=list(color_map.keys()),
                                            range=list(color_map.values())),
                              legend=alt.Legend(title='Project'))
            )

            # 7-day MA as line
            line_7 = base.transform_filter(
                alt.datum.Type == '7-day avg'
            ).mark_line(strokeWidth=2).encode(
                y='value:Q',
                color=alt.Color('Project:N',
                              scale=alt.Scale(domain=list(color_map.keys()),
                                            range=list(color_map.values())),
                              legend=None),
                strokeDash=alt.value([5, 5])
            )

            # 30-day MA as thicker line
            line_30 = base.transform_filter(
                alt.datum.Type == '30-day avg'
            ).mark_line(strokeWidth=3).encode(
                y='value:Q',
                color=alt.Color('Project:N',
                              scale=alt.Scale(domain=list(color_map.keys()),
                                            range=list(color_map.values())),
                              legend=None)
            )

            chart = (bars + line_7 + line_30).properties(height=400)
            st.altair_chart(chart, width='stretch')

            st.caption("Bars: Daily changes | Dashed: 7-day average | Solid: 30-day average")
        else:
            st.info("Not enough data to calculate velocity")
    else:
        st.info("No data available yet")


def display_productivity_stats(storage: MetricsStorage, projects: list):
    """Display productivity statistics cards.

    Args:
        storage: Metrics storage instance
        projects: List of project dictionaries
    """
    if not projects:
        return

    project_names = {p['id']: p['name'] for p in projects}
    processed_df = storage.get_processed_metrics(project_names, "word_count")

    if not processed_df.empty:
        # Calculate daily changes
        daily_changes = processed_df.diff()
        daily_sum = daily_changes.resample('D').sum()

        # Remove days with no activity
        daily_sum = daily_sum[(daily_sum != 0).any(axis=1)]

        if not daily_sum.empty:
            # Calculate statistics across all projects
            total_daily = daily_sum.sum(axis=1)

            best_day = total_daily.idxmax()
            best_day_words = int(total_daily.max())

            worst_day = total_daily[total_daily > 0].idxmin() if (total_daily > 0).any() else None
            worst_day_words = int(total_daily[total_daily > 0].min()) if (total_daily > 0).any() else 0

            avg_words = int(total_daily[total_daily > 0].mean()) if (total_daily > 0).any() else 0

            # Calculate streak (consecutive days with progress)
            current_streak = 0
            max_streak = 0
            temp_streak = 0

            dates = daily_sum.index.date
            today = pd.Timestamp.now().date()

            for i, date in enumerate(dates):
                if total_daily.iloc[i] > 0:
                    temp_streak += 1
                    max_streak = max(max_streak, temp_streak)

                    # Check if this is part of current streak
                    if i == len(dates) - 1 or date == today:
                        current_streak = temp_streak
                else:
                    temp_streak = 0

            # Display stats
            cols = st.columns(4)

            with cols[0]:
                st.metric(
                    label="📈 Best Day",
                    value=f"{best_day_words:,} words",
                    delta=best_day.strftime('%Y-%m-%d')
                )

            with cols[1]:
                if worst_day:
                    st.metric(
                        label="📉 Slowest Day",
                        value=f"{worst_day_words:,} words",
                        delta=worst_day.strftime('%Y-%m-%d')
                    )
                else:
                    st.metric(label="📉 Slowest Day", value="N/A")

            with cols[2]:
                st.metric(
                    label="⚡ Avg per Day",
                    value=f"{avg_words:,} words"
                )

            with cols[3]:
                st.metric(
                    label="🔥 Longest Streak",
                    value=f"{max_streak} days",
                    delta=f"Current: {current_streak}" if current_streak > 0 else "Not active"
                )
        else:
            st.info("Not enough activity data for statistics")
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
            with st.container(border=True):
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

                    # Convert UTC to German timezone
                    last_update_german = summary['last_update'].replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Berlin'))
                    st.caption(f"Last updated: {last_update_german.strftime('%Y-%m-%d %H:%M')}")

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
                    st.info("The metrics will be collected on the next scheduled run (every 20 minutes).")
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

    st.caption("Metrics are extracted every 30 minutes, you can trigger a manual extraction below.")

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


def sidebar_project_selector(config: Config):
    """Sidebar section for selecting which projects to display.

    Args:
        config: Configuration instance

    Returns:
        List of selected project dictionaries
    """
    projects = config.get_projects()

    if not projects:
        return []

    st.sidebar.header("Project Filter")
    project_names = [p['name'] for p in projects]

    # Check if there's a URL parameter specifying a featured project
    query_params = st.query_params
    default_selection = project_names  # Default: all projects

    # If 'project' parameter exists in URL, use it as default (case-insensitive)
    if 'project' in query_params:
        featured_project_param = query_params.get('project')

        # Case-insensitive matching
        matched_project = None
        for name in project_names:
            if name.lower() == featured_project_param.lower():
                matched_project = name
                break

        # If a valid project was found, select only that one
        if matched_project:
            default_selection = [matched_project]
        # Otherwise, fall back to all projects

    # Use multiselect for choosing which projects to display
    selected_project_names = st.sidebar.multiselect(
        "Select projects to display",
        options=project_names,
        default=default_selection,
        help="Choose which projects you want to see in the dashboard"
    )

    # Filter projects based on selection
    selected_projects = [p for p in projects if p['name'] in selected_project_names]

    return selected_projects


def main():
    """Main application."""
    st.title("📚 Thesis Progress Tracker")
    st.markdown("Track your Overleaf thesis progress with automated word and page counts")

    # Initialize components
    config, sync, storage = initialize_components()

    # Sidebar
    selected_projects = sidebar_project_selector(config)
    st.sidebar.divider()
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
        2. Metrics are automatically extracted every 30 minutes via cron
        3. View your progress over time in the charts below

        **Note:** Make sure the `extract_metrics.py` script is running via cron.
        """)
        return

    # Check if any projects are selected
    if not selected_projects:
        st.warning("Please select at least one project to display from the sidebar.")
        return

    # Display current metrics
    st.header("Current Status")
    display_project_cards(storage, selected_projects)

    st.divider()

    # Display charts
    st.header("Progress Over Time")

    # Cumulative progress charts side by side
    st.subheader("Cumulative Progress")
    col1, col2 = st.columns(2)

    with col1:
        plot_metrics_over_time(storage, selected_projects, "word_count")

    with col2:
        plot_metrics_over_time(storage, selected_projects, "page_count")

    st.divider()

    # Daily changes side by side
    st.subheader("Daily Changes")
    col3, col4 = st.columns(2)

    with col3:
        plot_daily_change(storage, selected_projects, "word_count")

    with col4:
        plot_daily_change(storage, selected_projects, "page_count")

    st.divider()

    # Productivity Analytics
    st.header("📊 Productivity Analytics")

    # Statistics cards
    st.subheader("Performance Summary")
    display_productivity_stats(storage, selected_projects)

    st.divider()

    # Writing velocity
    st.subheader("Writing Velocity")
    plot_writing_velocity(storage, selected_projects, "word_count")


if __name__ == "__main__":
    main()
