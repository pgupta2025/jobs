import json
import os
import re
import sys
import urllib.request

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
STATE_FILE = "state.json"

GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

PROFILE_ROLE = "ETL / QA Test Specialist"
PROFILE_YEARS = "9 years experience"
PROFILE_LOCATION = "India"
PROFILE_SKILLS = [
    "SQL", "PL/SQL", "AWS (S3, Glue, Athena)", "Snowflake", "PySpark",
    "Apache Airflow", "Power BI", "Data Warehousing", "JIRA", "STLC",
]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"seen_links": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def call_gemini(seen_links):
    prompt = f"""Search the web right now for current, open job postings in {PROFILE_LOCATION} for a {PROFILE_ROLE} with {PROFILE_YEARS}.
Skills to match against: {', '.join(PROFILE_SKILLS)}.
Search across LinkedIn Jobs, Naukri, Indeed India, Foundit (Monster India), Instahyre, and Cutshort. Look for titles like "ETL Tester", "QA Engineer - Data", "Data Warehouse Tester", "Test Analyst - ETL", "Data Quality Analyst", "SDET - Data".
Skip any of these already-seen links: {', '.join(seen_links[-200:]) if seen_links else '(none yet)'}.
Return ONLY a raw JSON array (no markdown fences, no prose, no commentary before or after) of up to 12 objects shaped exactly like:
{{"title": "...", "company": "...", "platform": "LinkedIn|Naukri|Indeed|Foundit|Instahyre|Cutshort|Other", "location": "...", "link": "https://...", "why": "one short sentence on why it matches"}}
If nothing new, return []."""

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }).encode()

    req = urllib.request.Request(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"Gemini API error {e.code}: {err_body}", file=sys.stderr)
        raise

    candidates = data.get("candidates", [])
    if not candidates:
        print("No candidates in Gemini response:", json.dumps(data)[:500], file=sys.stderr)
        return []

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(p.get("text", "") for p in parts)

    match = re.search(r"\[[\s\S]*\]", text)
    return json.loads(match.group(0)) if match else []


def notify(job):
    title = f"{job.get('title', 'New role')} @ {job.get('company', '')}"
    lines = [
        job.get("why", ""),
        f"{job.get('platform', '')} · {job.get('location', '')}",
    ]
    message = "\n".join(l for l in lines if l)
    link = job.get("link", "")

    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Click": link,
            "Priority": "default",
            "Tags": "briefcase",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30)


def main():
    state = load_state()
    seen = set(state.get("seen_links", []))

    jobs = call_gemini(list(seen))
    new_jobs = [j for j in jobs if j.get("link") and j["link"] not in seen]

    for job in new_jobs:
        try:
            notify(job)
            seen.add(job["link"])
        except Exception as e:
            print(f"Failed to notify for {job.get('link')}: {e}", file=sys.stderr)

    state["seen_links"] = list(seen)[-500:]  # cap growth
    save_state(state)
    print(f"Scan complete. {len(new_jobs)} new job(s) pushed.")


if __name__ == "__main__":
    main()
