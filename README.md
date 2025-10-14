# Overleaf Progress Tracker

A Streamlit-based dashboard for tracking thesis writing progress from Overleaf projects. Automatically fetches word counts and page counts over time, providing visual insights into your writing progress.

## Features

- **Automated Tracking**: Hourly updates via Git integration with Overleaf
- **Word Count**: Uses TeXcount for accurate word counting (same as Overleaf)
- **Page Count**: Compiles PDFs to determine actual page counts
- **Multi-Project Support**: Track multiple theses/papers simultaneously
- **Visual Dashboard**: Interactive charts showing progress over time
- **Easy Project Management**: Add/remove projects directly from the UI
- **Docker Deployment**: Fully containerized with all dependencies included

## Prerequisites

- Overleaf Premium account (for Git access)
- Docker and Docker Compose installed
- Overleaf authentication token

## Quick Start

### 1. Get Your Overleaf Token

1. Log in to your Overleaf account
2. Go to Account Settings
3. Find "Git Integration" section
4. Generate or copy your Git token

### 2. Clone and Configure

```bash
git clone https://github.com/yourusername/overleaf-progress.git
cd overleaf-progress

# Create .env file from example
cp .env.example .env

# Edit .env and add your Overleaf token
nano .env
```

### 3. Start the Application

```bash
# Build and start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access the Dashboard

Open your browser and navigate to: `http://localhost:8501`

## Usage

### Adding a Project

1. In the sidebar, find "Add New Project"
2. Enter your Overleaf Project ID (from the project URL)
3. Give it a display name (e.g., "Alice's Thesis")
4. Click "Add Project"
5. The system will clone the project and calculate initial metrics

### Finding Your Project ID

Your Overleaf project URL looks like:
```
https://www.overleaf.com/project/123456789abcdef
```

The project ID is: `123456789abcdef`

For Git access, the URL is:
```
https://git.overleaf.com/123456789abcdef
```

### Viewing Progress

- **Current Status**: Cards showing latest word and page counts
- **Progress Charts**: Word count and page count trends over time
- **Recent Updates**: Table of latest metric updates

### Manual Updates

Click the "Update Now" button in the sidebar to trigger an immediate update outside the regular schedule.

### Adjusting Update Interval

Use the slider in the Settings section to change how frequently updates occur (default: 60 minutes).

## Project Structure

```
overleaf-progress/
├── app.py                  # Main Streamlit application
├── src/
│   ├── config.py          # Configuration management
│   ├── overleaf_sync.py   # Git synchronization
│   ├── metrics.py         # Word/page count calculation
│   ├── storage.py         # SQLite data storage
│   └── scheduler.py       # Background scheduler
├── data/                   # Data directory (created on first run)
│   ├── config.json        # Project configuration
│   ├── metrics.db         # SQLite database
│   └── projects/          # Cloned Overleaf projects
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker Compose configuration
├── requirements.txt       # Python dependencies
└── .env                   # Environment variables (create from .env.example)
```

## Local Development (Without Docker)

### Requirements

- Python 3.11+
- TeX Live (full installation)
- Git

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export OVERLEAF_TOKEN=your_token_here

# Run application
streamlit run app.py
```

### Installing TeX Live

**macOS:**
```bash
brew install --cask mactex
```

**Ubuntu/Debian:**
```bash
sudo apt-get install texlive-full
```

**Windows:**
Download from https://www.tug.org/texlive/

## Configuration

### Environment Variables

- `OVERLEAF_TOKEN`: Your Overleaf Git authentication token (required)

### Update Interval

Default: 60 minutes. Adjustable via the dashboard settings or by modifying `data/config.json`.

## Data Persistence

All data is stored in the `data/` directory:

- `config.json`: Project list and settings
- `metrics.db`: SQLite database with historical metrics
- `projects/`: Git clones of Overleaf projects

This directory is mounted as a volume in Docker to persist data across container restarts.

## Troubleshooting

### "texcount not found"

Ensure TeX Live is properly installed. In Docker, this should be automatic. For local development, install TeX Live.

### "Failed to clone project"

- Verify your Overleaf token is correct
- Ensure you have access to the project (owner or collaborator)
- Check that the project ID is correct

### "Compilation failed"

- Check the LaTeX project compiles in Overleaf
- Missing packages will cause compilation failures
- Check container logs: `docker-compose logs`

### Port already in use

If port 8501 is already in use, modify `docker-compose.yml`:

```yaml
ports:
  - "8502:8501"  # Change 8502 to any available port
```

## Multiple User Tracking

To track projects from multiple users:

1. The Overleaf account with the token must be added as a collaborator on each project
2. Add each project using its project ID
3. All projects will be tracked and displayed together

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

See LICENSE file for details.

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Uses [TeXcount](https://app.uio.no/ifi/texcount/) for word counting
- Inspired by the need to track thesis writing progress

## Support

If you encounter issues, please open an issue on GitHub.
