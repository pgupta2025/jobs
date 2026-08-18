# Job Pipeline — Auto Scanner

Scans LinkedIn, Naukri, Indeed India, Foundit, Instahyre, and Cutshort twice a
day for ETL/QA testing roles matching your profile, and pushes new matches
straight to your phone via ntfy — free, no server of your own required.

## One-time setup (10 minutes)

1. **Get an Anthropic API key**
   Go to https://console.anthropic.com → Settings → API Keys → Create Key.
   Copy it (you won't see it again). Note: this uses paid API credits, not
   your Claude.ai subscription — usage here is small (2 calls/day), typically
   a few cents a month.

2. **Install ntfy and pick a topic**
   Install the ntfy app (iOS/Android) or use ntfy.sh in a browser.
   Pick a private, hard-to-guess topic name, e.g. `piyush-etl-jobs-8x2k`.
   Subscribe to that topic in the app. Anyone who knows the exact topic name
   can read your notifications, so don't use something guessable like
   `piyush-jobs`.

3. **Create a free GitHub repo**
   github.com → New repository → name it e.g. `job-pipeline` → Private is fine.

4. **Upload these 3 files to the repo root:**
   - `job_scan.py`
   - `state.json`
   - `.github/workflows/scan.yml`  (the `scan.yml` file goes inside a
     `.github/workflows/` folder — create that folder path when uploading)

5. **Add your secrets**
   In the repo: Settings → Secrets and variables → Actions → New repository secret
   - `ANTHROPIC_API_KEY` → paste your key from step 1
   - `NTFY_TOPIC` → your topic name from step 2 (just the name, not the full URL)

6. **Test it**
   Go to the Actions tab → "Scan for jobs" → Run workflow (this runs it once
   immediately instead of waiting for the schedule). Check your ntfy app for
   a notification if any new matching roles turned up.

That's it — after this it runs automatically every day at 9:30 AM and
5:30 PM IST and only notifies you when it finds something new.

## Adjusting things later
- **Change schedule:** edit the `cron:` line in `scan.yml` (uses UTC time)
- **Change skills/role searched:** edit the `PROFILE_*` variables at the top
  of `job_scan.py`
- **Reset "seen" history** (to get re-notified about old postings): clear
  `state.json` back to `{"seen_links": []}`
