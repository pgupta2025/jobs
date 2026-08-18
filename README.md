# Job Pipeline — Auto Scanner (free version, Gemini)

Scans LinkedIn, Naukri, Indeed India, Foundit, Instahyre, and Cutshort twice a
day for ETL/QA testing roles matching your profile, and pushes new matches
straight to your phone via ntfy. Runs on GitHub's free cron and Google's
free-tier Gemini API — no cost.

## One-time setup (10 minutes)

1. **Get a free Gemini API key**
   Go to https://aistudio.google.com/apikey → sign in with any Google account
   → Create API key. Copy it. The free tier is generous enough for 2 scans/day
   with plenty of room to spare.

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
   In the repo: Settings → Secrets and variables → Actions → Secrets tab →
   New repository secret
   - `GEMINI_API_KEY` → paste your key from step 1
   - `NTFY_TOPIC` → your topic name from step 2 (just the name, not the full URL)

6. **Test it**
   Go to the Actions tab → "Scan for jobs" → Run workflow (this runs it once
   immediately instead of waiting for the schedule). Check your ntfy app for
   a notification if any new matching roles turned up.

That's it — after this it runs automatically every day at 9:30 AM and
5:30 PM IST and only notifies you when it finds something new, at no cost.

## Adjusting things later
- **Change schedule:** edit the `cron:` line in `scan.yml` (uses UTC time)
- **Change skills/role searched:** edit the `PROFILE_*` variables at the top
  of `job_scan.py`
- **Reset "seen" history** (to get re-notified about old postings): clear
  `state.json` back to `{"seen_links": []}`

## If Gemini's free tier ever gets tight
If you hit rate limits on a busy day, either drop the scan schedule to once a
day in `scan.yml`, or switch `GEMINI_MODEL` in `job_scan.py` to a smaller
model. The free tier resets daily.
