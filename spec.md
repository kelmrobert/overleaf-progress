# Dashboard for Tracking Thesis Writing Progress (Overleaf Integration)

## Overview and Goals

We plan to build a Streamlit-based dashboard to visualize writing progress for one or more Overleaf projects (e.g. multiple theses). The dashboard will display key metrics – primarily word count and page count – over time, allowing comparisons between multiple people's projects. The solution should require minimal effort to add new projects and run on a simple schedule (e.g. an hourly update job). We will also containerize the setup with Docker for easy deployment.

### Key Requirements and Challenges

- **Retrieving Overleaf data**: We need a way to programmatically fetch the LaTeX source (or metrics) from an Overleaf project. Overleaf doesn't provide an open public API for free accounts, but it offers Git integration for premium users and third-party tools for others. We want to avoid cumbersome manual steps like constantly downloading zip files.

- **Automating updates**: The process should run periodically (e.g. hourly) to pull the latest changes without manual intervention.

- **Metrics calculation**: We must compute the total word count (excluding LaTeX commands) and number of pages from the latest thesis content.

- **Multi-project support**: The system should handle multiple projects in parallel and make it easy to add or remove projects (possibly via the dashboard UI itself).

- **Visual dashboard**: Create a clear, visually appealing dashboard (using Streamlit) with charts of progress over time and summary stats for each project.

---

## 1. Retrieving Overleaf Project Data

### Option A: Overleaf Git Integration (Premium)

If the Overleaf account has premium features, the simplest approach is to use Overleaf's built-in Git interface. Overleaf premium allows obtaining a special Git URL for each project, treating the project like a remote Git repository. We can clone the project locally and then periodically pull changes to get updates. Overleaf's Git backend essentially commits changes made in the online editor so they can be pulled. Each project has a unique Git URL (e.g. `https://git.overleaf.com/<projectID>`).

**Authentication**: Overleaf uses token-based auth for Git access. We generate an Overleaf authentication token from the account settings (one token can access all projects on that account). In Git operations, use username "git" and the token as the password. For non-interactive use, we can embed the token in the clone URL or use a Git credential helper so the script isn't prompted each time. This avoids manually entering credentials on each pull.

**Collaborator access**: If multiple people's projects are tracked, one approach is to have the main Overleaf account be added as a collaborator on each friend's project. As long as the tracking account has access (and premium to use Git), it can clone those projects as well. The same token works for all accessible projects. Each project ID/repo URL would be configured in the app. This way, friends don't have to share their credentials, only invite the tracking account to their Overleaf projects.

### Option B: GitHub Sync (Less Automated)

Overleaf also offers GitHub repository sync for premium users, but this is not ideal for continuous tracking. Overleaf's GitHub integration requires manual syncing (via the Overleaf menu) and does not auto-push changes on its own. For example, Overleaf will only push or pull when a user clicks "Sync" in the project menu, and it doesn't continuously update in real-time. This means we could miss changes between syncs. While one could link each thesis to a GitHub repo and then have our program pull from GitHub, it introduces an extra manual step for the user. Therefore, unless automatic sync is somehow scripted, this is a less simple route. We will prefer direct Overleaf access unless the user is already disciplined in pushing changes regularly.

### Option C: Overleaf API/Tools (Free accounts)

If premium Git access is not available, we can use unofficial tools to fetch Overleaf data. Notably, there are Python packages that interface with Overleaf's backend:

- **PyOverleaf**: an unofficial Python API/CLI that can list projects and download files directly. It works by using your Overleaf login session (via browser cookies or login) to fetch project contents. Using PyOverleaf, one could log in once and then call an API to download the project as a .zip (source files) programmatically. This avoids needing Overleaf's official Git feature.

- **overleaf-sync**: a tool that provides two-way sync for Overleaf without a paid account. It launches a headless browser for the user to log in (storing an auth cookie), then can download or upload files. We could script it to pull changes periodically. Overleaf-sync even has a command to download the compiled PDF from Overleaf, which could be useful for getting page counts directly (more on this later). This tool emphasizes it works with free accounts (no Git/Dropbox needed).

Using these tools requires a bit more setup for authentication (e.g. the first run might prompt for login in a browser or via a GUI to solve CAPTCHA). For a headless server environment, one might need to simulate or reuse a session cookie. If going this route, we would integrate the library in our Python code. For example, using PyOverleaf: call `Api.login_from_browser()` once to store credentials, then use `api.get_projects()` and `api.download_project(project_id)` to fetch the latest sources. This could be run hourly just like a Git pull. The downside is complexity of maintaining login sessions; however, since Overleaf-sync/pyoverleaf handle cookies, it's feasible.

**Decision**: If possible, we will use Overleaf's Git integration (Option A) for simplicity, as it's robust and meant for automation. The program will accept an Overleaf project ID (or Git URL) and use the token to clone/pull updates. If the user doesn't have premium, a fallback is to incorporate PyOverleaf or a similar tool to fetch the project. In either case, the concept is to retrieve the latest .tex files for each project on a schedule.

---

## 2. Scheduled Data Extraction (Hourly Job)

We will implement an automated job (running hourly) to update the data. There are a couple of ways to do this:

### Within the Python App

We can use a scheduler library (like `schedule` or `APScheduler`) or a simple loop in a thread to periodically trigger data retrieval. For example, start a background thread when the app launches that wakes up every hour, performs the update, then sleeps. This approach keeps everything in one process (the Streamlit app). We must ensure thread-safety if the Streamlit UI thread reads data at the same time; using locks or Streamlit's caching mechanisms can help.

### External Cron Job

Alternatively, run a separate script or process (perhaps in the same Docker container via cron or a supervisor process) that performs the hourly updates and writes results to a file or database. The Streamlit app would then simply read the updated data file to display the latest info. This decouples data collection from the UI. It adds a bit of deployment complexity (ensuring cron is set up in Docker, etc.), but can be more robust for long-term scheduling.

For simplicity, we might choose the first approach (especially if using Streamlit Cloud or similar, where background threads are allowed). The hourly routine will do the following for each project:

### Pull Latest Changes

If using Git, perform a `git pull` on the repository clone for that project. This will fetch any new commits from Overleaf. (The first time, we'll do a `git clone` to set up the repo; subsequent runs use pull to update.) If using PyOverleaf/overleaf-sync, then download the latest source (e.g. by re-downloading the zip or syncing changes). These operations are lightweight if no changes occurred, and ensure we have the newest .tex content.

### Word Count Calculation

After updating the source, run a word count on the LaTeX files. Overleaf's own word count feature uses the TeXcount utility, which ignores LaTeX commands and counts only meaningful words. We will mimic this for accuracy. We can invoke TeXcount on the main TeX file: e.g. `texcount -merge -sum main.tex` (the `-merge` flag ensures it includes `\input`/`\include` files, similar to Overleaf). The output of TeXcount can be parsed to get the total word count. There are two ways to integrate TeXcount:

- Call it as an external command (if TeXcount is installed, it's a Perl script included with TeX Live) and capture the output.

- Use a Python library or write a simple parser to strip TeX commands and count words. However, using the proven tool is preferable to handle edge cases. Overleaf's docs confirm it runs texcount on the main file and included files, so our count will align with Overleaf's definition of a word count.

### Page Count Calculation

We need the number of pages of the compiled PDF. This likely requires compiling the LaTeX (unless we use an Overleaf API to get the PDF). The straightforward method is to run a LaTeX engine on the source. We will use a LaTeX compiler inside our Docker container (e.g. `latexmk` with pdfLaTeX). After pulling updates, run `latexmk -pdf -quiet main.tex` to compile the project. This will produce `main.pdf` (and do nothing if no changes since last compile, thanks to latexmk). Once compiled, determine the page count by either:

- **Parsing the LaTeX log**: The compiler's log file usually contains a line like "Output written on main.pdf (xx pages)". We can search for "pages" in the log to find the number of pages generated. This avoids needing extra PDF tools.

- **Reading the PDF**: Alternatively, open the PDF and get its page count. We could use a Python PDF library (such as PyPDF2 or PyMuPDF) to read `main.pdf` and count pages. This is straightforward and reliable if we have the PDF. Since we will have compiled it, this is fine. (If we did not want to compile locally, note that the overleaf-sync tool can fetch the compiled PDF from Overleaf's servers. But given we are already installing TeX for word count, local compile is reasonable and avoids relying on Overleaf's compilation frequency.)

**Efficiency**: Compiling every hour is generally fine for a typical thesis (~several dozen pages) – pdflatex should run in a few seconds. If needed, we can compile in "draft" mode or detect if content changed significantly before compiling. However, since we're pulling via Git, we can check if there was a new commit. If no changes were pulled, we can skip recompiling and reuse the previous page count to save time. This logic can be built in (e.g. store the last commit hash or a timestamp of last word count).

### Record the Metrics

Once we have the word count and page count for the project, we save these along with a timestamp. We'll maintain a time-series of progress for each project. For example, we can append a line to a CSV or JSON file: `project_id, date_time, words, pages`. Over time, this builds a history that can be plotted. If using a database (even a simple SQLite), we could insert a row per reading. For simplicity, a CSV or JSON per project (or one combined CSV with project as a column) is easy to manage. The data structure could also be kept in memory (e.g. a Python dictionary of project -> list of (time, words, pages)), but persisting to disk ensures we don't lose history if the app restarts.

**Repeat**: The scheduler will repeat this process every hour. The interval can be adjusted (it could even be every few minutes during active writing, but hourly is a good default).

**Note on multiple projects**: The update loop will iterate through all configured projects. It should handle each independently so one slow compile doesn't block the rest unnecessarily (though they could be run sequentially or in parallel threads if needed). The results for each project are stored separately but in the same manner.

---

## 3. Data Management and Storage

To keep the system easy to extend, we'll implement a simple way to manage the list of tracked projects and store their progress data:

### Project Configuration

We will maintain a list of projects to track. Each entry might include an identifier and a display name. For Overleaf Git, the project's unique ID (from its URL) or Git URL is needed; for other methods, perhaps the project name as known to the API. We can start by hard-coding or reading from a config file (e.g. a JSON listing projects). However, the user specifically wanted to make adding projects "no big effort" and even suggested adding via the Streamlit UI. We can achieve this by providing an "Add Project" form in the app where a user can input the Overleaf project ID (and perhaps a nickname for it). When submitted, the app can initiate a clone of that project (using the stored token) and add it to the tracking list. This new project info should be persisted (maybe appended to the config file or saved in a small local database) so that it remains tracked on restarts.

### Storing Historical Metrics

Each time the job runs, append the new data point to a storage. A CSV file per project (named with project id or name) could work: it's human-readable and easy to load with pandas. Alternatively, a single CSV with an extra column for project name would allow all data in one file. Another approach is using SQLite, creating a table for project info and a table for measurements (columns: `project_id, timestamp, word_count, page_count`). SQLite is lightweight and avoids file handling issues if multiple threads write simultaneously (it handles locks). Given the scale (maybe a few data points per hour per project), either is fine.

### Data Access in the App

The Streamlit app, on each page load or on a refresh button, will load the latest data from storage. We might also keep a cached copy in memory that the background thread updates, to avoid disk I/O on every UI render. Streamlit's `st.cache_data` or `st.singleton` can help store state between runs. Ensuring that the UI always reflects the most recent scheduled update is important – we could implement a "Refresh data" button that forces a reload (in case the user is impatient between hourly updates). But if we run the background updates in the same process, we can have the UI automatically update via Streamlit's features (e.g. use `st.experimental_rerun()` or set up the thread to somehow trigger refresh). Simpler: just let the user refresh the page if needed, or rely on the fact that each hour new data will be written and our charts will update when re-rendered.

---

## 4. Word Count and Page Count Implementation

As noted, we will use TeXcount for word count and a TeX engine for page count. Here are more implementation details:

### TeXcount Integration

We should ensure TeXcount is installed in the environment. In a TeX Live distribution, `texcount.pl` is included. We can call it via command line. For example, after updating the project's files, run:

```bash
texcount -merge -sum -q main.tex > count.txt
```

This will produce a summary of word counts (the `-q` quiet flag minimizes detail). We can parse `count.txt` for the total word count. Typically, TeXcount outputs something like "Words in text: 1234" along with breakdowns. We'll extract the main total. If multiple files or bibliographies are included, `-merge` ensures they are counted together. If the main file isn't at project root, we might need to adjust or specify the path. (Overleaf requires the main .tex at top level for its own word count to work; we can either enforce that or allow a config specifying which file to count if needed.)

### LaTeX Compilation

We will call `latexmk` or `pdflatex`. Using `latexmk` is convenient because it will run pdflatex (and bibtex etc. if needed) the appropriate number of times until the document is up-to-date, then stop. We'll use the `-silent` or `-quiet` option to suppress verbose output. If the project is large, we might want to increase the interval rather than compile too frequently, but hourly should be fine. We need to have all the necessary LaTeX packages available in our environment (which we'll address in Docker setup). If a project fails to compile (e.g. due to a missing package or a TeX error), we should handle that gracefully – perhaps log the error to console and skip page count update for that round (keeping the last known page count). Word count can still proceed even if the TeX is temporarily not compiling, since word count doesn't need a successful compile.

### Page Count Extraction

After compilation, open the generated `main.log` file and search for a line containing "Output written on" which typically looks like:

```
Output written on main.pdf (120 pages, 5.0 MB).
```

We can regex-search for `\((\d+) pages\)` to capture the number. If found, that is our page count. Alternatively, if we prefer using a PDF library: use PyPDF2 in Python:

```python
from PyPDF2 import PdfReader
reader = PdfReader("main.pdf")
pages = len(reader.pages)
```

This gives the same result. Either method requires that `main.pdf` was produced. If compilation failed, we should detect that (no PDF updated) and perhaps keep the old value or mark it as NaN for that timestamp (but since Overleaf would likely be compiling error-free content most of the time, this may be rare).

### Validating Metrics

We might want to cross-check that our word count matches Overleaf's own count (for sanity). Overleaf's menu shows word count after compile; since we use the same texcount logic, it should match. If any discrepancy arises (e.g. if the user's document uses `\includeonly` or something special), we can adjust by using TeXcount options or including the BBL file as Overleaf does (notice Overleaf passes `output.bbl` to texcount to include bibliography words if needed). We can incorporate similar if counting refs is desired. But likely just the main text word count is enough.

---

## 5. Dashboard Design with Streamlit

We will create the front-end using Streamlit, which allows rapid development of interactive dashboards in Python. The dashboard will present both current summary metrics and historical trends:

### Layout

- **At the top**: a title and maybe a short description (e.g. "Thesis Writing Progress Tracker"). Possibly include controls to select timeframe (last week, last month, all time) for the charts, if the data spans a long period.

- **Add Project Form**: If we implement adding projects via UI, a sidebar or top section will have input fields. For example, Project ID (or a share URL) and Project Name (a friendly name or person's name). On submit, the app will trigger the clone/pull for that project and update the configuration. This might require a page reload. (We'll need to ensure the background job becomes aware of the new project – if the job reads from a config file each cycle, it will pick it up next hour. We could also trigger an immediate data fetch so it appears right away on the dashboard.)

- **Summary Statistics**: We can use Streamlit's metric or columns to display the latest word count and page count for each project. For instance, show a card or column with the project name, the current word count, and the current page count. We might also display the difference since last update or since yesterday (Streamlit's `st.metric` allows showing a delta). This would let viewers see how much was written recently. For example, "Alice's Thesis – 10,200 words (+150 today), 42 pages (+1)". This adds a bit of competitive/comparative aspect for friends. We'd calculate the delta by comparing the most recent count to the count 24 hours ago (if data available).

- **Historical Charts**: Below the summary, we'll have charts plotting the progress over time. We can create one chart for word count and one for page count, each chart containing lines for each project (multi-line chart). Using Pandas and Streamlit's built-in charting: if we prepare a DataFrame where the index is time and columns are the word counts for each project, `st.line_chart(df)` will plot all lines with a legend. This gives an overview of how each person's word count is growing over the weeks. Similarly for pages. We should label axes (Date vs Word Count). Streamlit by default will use the DataFrame index (which can be datetime) on the x-axis. For better appearance, we might use an Altair chart for more control – for example, to color lines and add tooltips on hover showing exact values. Altair or Plotly can also allow interactive features (like toggling a series on/off). But for a simple setup, the default `line_chart` is fine and quick.

- **Filtering**: We may include checkboxes or multiselect so the user can choose which projects to display (in case many projects are tracked, one might want to compare just two at a time). Streamlit can dynamically filter the DataFrame based on selection.

- **Comparison and rankings**: If desired, we could add a section that ranks projects by current word count or shows a bar chart of total words written so far per project. This is more of a fun addition – e.g. "Alice vs Bob: who wrote more?". Since the primary goal is tracking one person's progress, this is optional, but could motivate if friends are comparing. A simple table or bar chart of current counts could accomplish this.

### Styling

We aim for a clean, uncluttered design using Streamlit's default theme (which is already clean) with perhaps some custom CSS for minor tweaks if needed. We will keep paragraphs of text minimal in the dashboard – mainly focusing on numbers and visuals for quick scanning. Headings and subheadings in the app will separate sections (e.g. Overall Summary, Trends). Each project's data could be in a separate expandable section if we want to show more details (like separate chart per project), but probably a combined chart is more insightful for comparison.

### Realtime Considerations

Streamlit apps aren't push-update by default, but we can use `st.experimental_data_editor` or just auto-refresh the page periodically. A simple way is to have the app periodically rerun (Streamlit can rerun script if any widget value changes; one hack is to use `st.experimental_rerun()` on a timer thread, or instruct users to use the refresh button). Since our updates are hourly, it's enough that whenever someone opens the app or hits refresh, they'll see the latest data (assuming the background job updated it recently). We could even display the last update timestamp on the dashboard ("Last updated at 14:00 CET") to inform users.

---

## 6. Adding New Projects via the Dashboard

To fulfill the requirement that adding projects is very simple (possibly through the UI), we will implement the following:

A sidebar form with fields for the new project. For Overleaf Git, the user can paste the Overleaf project URL (or just the project ID number). If using an Overleaf API method, maybe the user provides the exact project name as shown in Overleaf (the script could search the list for that name). We'll also have a text input for a "Display Name" (like the person's name or project nickname) which we'll use in the dashboard labels.

When the user submits the form, the app will:

- **If using Git**: construct the clone URL (e.g. `https://git.overleaf.com/<ID>`) and run a `git clone` command with authentication. This will create a local folder for that project's files. We should assign a short folder name (perhaps based on the project name or the person's name, to keep things organized). We only clone once at addition; subsequent updates use pull.

- **Add an entry to the project list** (in memory and in the persistent config). For example, update the JSON config file to include this new project and name. This ensures the background scheduler knows about it. If the scheduler loop reads the project list fresh each cycle, it will pick up the addition on the next cycle. We can also immediately trigger the word count/page count for the new project so that it appears on the dashboard without waiting an hour. (This could be done by calling the same functions the scheduler uses, right after cloning.)

- **Provide feedback on the UI** (e.g. a success message: "Project X added successfully and initial data collected." or error if clone failed).

We will need to handle the case where the Overleaf token is required. Likely we have the token stored as an environment variable or secret in the app. The clone command will use it automatically (if we have a global Git credential helper configured with the token, or by embedding in URL). If clone fails due to auth, we should show an error asking to check the token.

If using the Overleaf API approach instead, adding a project might just mean adding its ID to the list and the next cycle will download it. In that case, we don't need to "clone" per se, just mark it for syncing. The heavy lifting (download) would occur on the next scheduled run or immediately if triggered.

### Removal of Projects

We might also allow removing a project from tracking (for instance, if a friend's thesis is done). This could be a button in the UI next to each project's name to stop tracking. Implementation would involve removing it from config and perhaps deleting its local clone folder to save space. This is a nice-to-have, but not strictly requested; we mention it for completeness.

By providing an in-app way to add projects, we ensure "no big effort" is needed – no code change, just a few clicks. Under the hood, it edits the config that the Docker container can persist (perhaps by mounting a volume for the config and clones).

---

## 7. Docker Setup and Environment

We will containerize the entire application so it's easy to run on any machine without manual dependency installation. The Docker setup will include all components: Python environment, TeX tools, and the Streamlit app.

### Base Image

We can start from a Python 3 base image (e.g. `python:3.10-slim`). On top of this, we will need to install additional packages:

### TeX Live

For LaTeX compilation and TeXcount. We can install a TeX Live distribution via apt. For a full guarantee (covering all packages the thesis might use), we might use `texlive-full` (though it is large ~2GB). If we want to reduce image size, we could use a more minimal set (`texlive-latex-recommended`, `texlive-latex-extra`, `texlive-fonts-recommended`, and any specific packages like `texlive-bibtex-extra` if needed for bibliography). But to be safe and simple, `texlive-full` ensures any Overleaf template will compile (Overleaf itself has a full TeX environment). We also get `latexmk` and `texcount` as part of this. Another alternative is to use a tiny TeX distribution (like TinyTeX or Tectonic) to compile on the fly, but that adds complexity. We'll proceed with standard TeX Live for reliability.

### Git

Install `git` (for Option A retrieval). This is needed to clone/pull Overleaf repositories inside the container. We'll also configure Git to use the token – likely by using an environment variable. One approach is to set up a `.netrc` or Git credential helper inside the container that contains:

```
machine git.overleaf.com
login git
password <YOUR_TOKEN>
```

This way git will automatically authenticate. If security is a concern, the token can be provided via an environment variable when running the container (and the entry created on startup). Alternatively, use the `GIT_ASKPASS` mechanism to supply the token. For simplicity, embedding token in the clone URL (as `https://git:<token>@git.overleaf.com/projectID`) might be easiest – we just have to be careful not to log that URL. Since the token is effectively a password, we will treat it securely (not hard-code in the image). Instead, we'll pass it as an environment variable `OVERLEAF_TOKEN` when running the container, and our app can construct auth URLs using it.

### Python Libraries

In the Dockerfile or requirements, include:

- `streamlit` (for the app UI).
- `pandas` (for data manipulation and charts).
- `PyPDF2` or `pypdf` (if we choose to parse PDF for page count).
- If using PyOverleaf or overleaf-sync: install those (`pyoverleaf`, or `overleaf-sync` via pip). Note that `overleaf-sync` may require a Qt dependency for the mini browser – likely not straightforward in a slim container. PyOverleaf relies on reading browser cookies; that might need the `browsercookie` dependency (which is mentioned in its README). If using Overleaf Git, we might not need these Python libs at all. We will likely omit them if using Git integration to keep the image smaller and simpler. They are backups if needed.
- Possibly `schedule` or `APScheduler` if we want a clean scheduling in code. Or we can manage with a loop + sleep.
- `matplotlib` or `altair` if we want custom plotting beyond Streamlit's defaults (though Streamlit can handle a lot itself). However, Altair comes by default with Streamlit as far as plotting, I believe. If not, we add `altair`.

(The TeX Live install will include Perl, so TeXcount will run. No need for a separate Perl install.)

### Entrypoint

The container will run the Streamlit app. In the Dockerfile `CMD`, we put something like:

```bash
streamlit run app.py --server.port 8501 --browser.gatherUsageStats=false
```

By default, Streamlit listens on 8501; we will expose that port. The `browser.gatherUsageStats=false` just disables telemetry.

### Docker Compose

If using an external cron, we might have a separate service for the scheduler. But it's probably unnecessary; we'll keep one container. The container can run both the app and background tasks if coded in one script. In Docker Compose, just one service mapping port 8501.

### Volume Mounting

It's wise to mount a volume for the project data and config, so that if the container is updated or restarted, we don't lose the git clones and history. For example, mount a host directory to `/data` inside the container, and configure our app to store git repos and CSV files in `/data`. This way, the data persists. (If that's not possible, the app will re-clone on restart and history would reset, which might be acceptable for short-term but not ideal for long tracking). We will document this in the setup instructions.

### Running the Container

The user will set the `OVERLEAF_TOKEN` environment variable (and possibly initial project IDs) when running `docker run`. We can allow initial project config via env or a file. Alternatively, instruct the user to use the Streamlit UI to add projects after launching. Because if no project is configured initially, the dashboard will be empty until they add one. We can start with none and show a message "Add a project to begin tracking."

---

## 8. Summary of Workflow

Putting it all together, the system will operate as follows:

### Initialization

Launch the Docker container. The Streamlit app starts. If configured with some projects (via file or previous state), it will load those and possibly immediately do an initial data fetch (especially on first run or if data files are empty). Otherwise, user uses the "Add Project" form to add their Overleaf project(s), which triggers clone and initial metric computation.

### Automated Updates

The scheduler (thread or external) runs every hour:

- For each project: do a `git pull` (or API sync) to get latest LaTeX source.
- Run TeXcount to update word count.
- Run LaTeX compile (if needed) to update page count.
- Append the new metrics to the data store (and possibly keep in memory).
- (We might also commit the changes or metrics to a separate git or backup if needed, but not necessary.)

### Dashboard Refresh

When a user views the dashboard, it reads the latest data. The line charts show the growth of word count and page count over time for each project. The numbers show current totals. Users can compare who is ahead or how their own work is progressing. If the user is actively writing and wants up-to-the-hour updates, they can simply refresh the page after an hour to see the increment. We can also allow manual triggering of an update via a "Update now" button that calls the update routine outside the schedule (useful if they just wrote a lot and want to see it immediately).

### Streamlit Interactivity

Users can add new projects at any time. They could also potentially pause tracking (not implemented, but could be done by removing). The interface is user-friendly with buttons and forms, avoiding the need to deal with the command line or editing files.

### Comparison and Motivation

By tracking multiple projects side by side, the friends can motivate each other. The app could even highlight the person with the highest word count or the fastest growth (for fun). This isn't required, but a small competitive element (like a "leaderboard" of words written this week) could be an interesting extension.

---

## Key Design Principles

Throughout this, we ensure the solution remains simple to maintain:

- Using Overleaf's Git or their provided mechanisms means we don't reinvent file syncing – it's a reliable method to get the latest text.

- Using standard tools (TeXcount, LaTeX) ensures accurate metrics in line with Overleaf's counts.

- Docker encapsulation means anyone can run the tracker without installing TeX or other dependencies on their machine, and Docker ensures the environment (LaTeX version, etc.) is consistent – important because different TeX versions could slightly alter page count or needed packages.

Finally, because we cite Overleaf's guidelines and existing tools, we have confidence the approach is feasible:

- Overleaf's Git access (premium) is documented and supports exactly our use case of pulling project content.

- Overleaf's own word count feature uses TeXcount, which we mirror.

- Third-party packages like overleaf-sync confirm that even without Git, it's possible to sync projects via Overleaf's web endpoints, so in any scenario we can retrieve the data one way or another.

No matter which retrieval method is used, the end result is a live-updating progress dashboard that requires little manual effort, uses Overleaf as the writing platform, and gives the user and their friends a clear picture of their thesis writing progress over time.