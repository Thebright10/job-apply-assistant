# Daily Job-Match & Application-Draft Assistant (Cloud + Dashboard version)

This version runs automatically every day **in the cloud** (GitHub Actions) — your laptop doesn't need
to be on — and reports results to a dashboard page you add to your portfolio.

## How the pieces fit together

```
GitHub repo (this one, private is fine)
  └─ GitHub Actions runs main.py daily
        ├─ drafts personalized applications
        ├─ saves Gmail drafts (via your GitHub Secrets, never in code)
        └─ writes dashboard_data.json + applied_log.csv, commits them back

Your portfolio repo (Portfolio_Sudip, public)
  └─ dashboard.html reads dashboard_data.json from this repo's raw GitHub URL
     and displays stats + recent matches
```

Nothing sends automatically — every application still lands as a draft you review before hitting Send.

## Setup

### 1. Create the new GitHub repo
- Go to github.com → New repository → name it e.g. `job-apply-assistant`
- **Private is recommended** (your `applied_log.csv` will list companies/jobs — not sensitive, but no
  need to make it public). Actions and Secrets both work fine on private repos.
- Upload all files from this folder (`main.py`, `profile_config.py`, `requirements.txt`,
  `.gitignore`, `dashboard.html`, and the `.github/workflows/daily-job-search.yml` folder) — keep the
  folder structure exactly as-is, especially `.github/workflows/`.

### 2. Add your credentials as GitHub Secrets (not in any file!)
In the new repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:
- `GMAIL_ADDRESS` → your Gmail address
- `GMAIL_APP_PASSWORD` → the 16-character App Password (see main setup guide for how to generate one)
- `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` → optional, for India-specific listings

### 3. Turn on Actions
Go to the **Actions** tab of the new repo → if prompted, click "I understand my workflows, enable them."
The workflow is already scheduled for 8:00 AM UTC daily — edit the `cron:` line in
`.github/workflows/daily-job-search.yml` if you want a different time (cron times are always UTC).

### 4. Test it manually
Actions tab → "Daily Job Search" workflow → **Run workflow** button → Run. Watch it go green.
After it finishes, you should see `applied_log.csv` and `dashboard_data.json` appear/update in the repo.

### 5. Add the dashboard to your portfolio
- Open `dashboard.html`, find these three lines near the bottom and fill in your real values:
  ```js
  const REPO_OWNER = "YOUR_GITHUB_USERNAME";
  const REPO_NAME  = "job-apply-assistant";
  const BRANCH     = "main";
  ```
- **If you made the automation repo private**, `raw.githubusercontent.com` won't serve the JSON to
  a public page without auth. Easiest fix: make just this one repo public (the data in it — job
  titles/companies/links — isn't sensitive), or ask me to switch the dashboard to pull from a small
  public "stats-only" repo instead if you'd rather keep the main one private.
- Copy `dashboard.html` into your `Portfolio_Sudip` repo (e.g. as `dashboard.html` at the root, or
  inside a `job-dashboard/` folder).
- Add a link to it from your portfolio's nav, e.g.:
  ```html
  <a href="dashboard.html">Job Search Bot</a>
  ```
- Commit and push — GitHub Pages will pick it up automatically.

## What you'll see on the dashboard
- Listings scanned today, new matches today, total applications drafted all-time
- A live "bot is running normally" status dot (turns red if the last run errored)
- A feed of recent matches, each linking to the original job post
- A "Run now on GitHub" button that takes you straight to the Actions run page

## Files in this repo
- `main.py` — the script (also writes `dashboard_data.json` now)
- `profile_config.py` — your info + search keywords
- `.github/workflows/daily-job-search.yml` — the daily cloud schedule
- `dashboard.html` — copy this into your portfolio repo
- `.gitignore` — keeps `.env` and personal draft text out of the repo
- `applied_log.csv` / `dashboard_data.json` — auto-created/updated by each run
