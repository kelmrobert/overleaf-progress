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

## How It Works

The application uses a simple, decoupled architecture:

1. **Cron Job**: Extracts metrics hourly via `extract_metrics.py`
2. **JSON Storage**: Stores all data in `data/metrics.json`
3. **Dashboard**: Read-only Streamlit app displays the data

This separation makes the system reliable and easy to understand.

## Project Structure

```
overleaf-progress/
├── app.py                  # Streamlit dashboard (read-only)
├── extract_metrics.py      # Standalone extraction script (run by cron)
├── src/
│   ├── config.py          # Configuration management
│   ├── overleaf_sync.py   # Git synchronization
│   ├── metrics.py         # Word/page count calculation
│   └── storage.py         # JSON file storage
├── data/                   # Data directory (created on first run)
│   ├── config.json        # Project configuration
│   ├── metrics.json       # Metrics data (JSON)
│   ├── extraction.log     # Extraction logs
│   └── projects/          # Cloned Overleaf projects
├── Dockerfile             # Docker with cron
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

# Run extraction manually (or set up local cron)
python3 extract_metrics.py

# Run dashboard
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
- `metrics.json`: Time-series metrics data (simple JSON)
- `extraction.log`: Logs from the extraction script
- `projects/`: Git clones of Overleaf projects

This directory is mounted as a volume in Docker to persist data across container restarts.

## Manual Extraction

To run the metrics extraction manually (outside the hourly schedule):

**Inside Docker container:**
```bash
docker exec overleaf-progress-tracker python3 /app/extract_metrics.py
```

**Or with docker-compose:**
```bash
docker-compose exec overleaf-tracker python3 /app/extract_metrics.py
```

**On local machine:**
```bash
python3 extract_metrics.py
```

**View logs:**
```bash
# Extraction log
docker exec overleaf-progress-tracker cat /app/data/extraction.log

# Cron log
docker exec overleaf-progress-tracker cat /app/data/cron.log

# Or from host (if data is mounted)
cat data/extraction.log
```

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

## Multiple Account Support

The tracker supports multiple Overleaf accounts without requiring collaborator access. You can provide multiple authentication tokens, and the system will automatically try each one until it finds the correct account for each project.

### Setup Multiple Accounts

1. **Get tokens from each account:**
   - Log into each Overleaf account
   - Go to Account Settings → Git Integration
   - Copy the Git token

2. **Configure multiple tokens:**
   ```bash
   # In your .env file, separate tokens with commas
   OVERLEAF_TOKEN=token_from_account1,token_from_account2,token_from_account3
   ```

3. **Add projects:**
   - Add any project ID from any account
   - The system will automatically try each token until one works
   - No need to specify which token belongs to which project

### How It Works

When cloning or accessing a project:
1. The system tries the first token
2. If access is denied, it automatically tries the next token
3. This continues until a token with access is found
4. The successful token is used for all future operations on that project

This approach allows you to track projects from multiple Overleaf accounts (personal, work, collaborations, etc.) without manual configuration.

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
