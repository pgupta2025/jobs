import json
import os
import re
import sys
import urllib.request

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
STATE_FILE = "state.json"

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


def call_claude(seen_links):
    prompt = f"""Search the web right now for current, open job postings in {PROFILE_LOCATION} for a {PROFILE_ROLE} with {PROFILE_YEARS}.
Skills to match against: {', '.join(PROFILE_SKILLS)}.
Search across LinkedIn Jobs, Naukri, Indeed India, Foundit (Monster India), Instahyre, and Cutshort. Look for titles like "ETL Tester", "QA Engineer - Data", "Data Warehouse Tester", "Test Analyst - ETL", "Data Quality Analyst", "SDET - Data".
Skip any of these already-seen links: {', '.join(seen_links[-200:]) if seen_links else '(none yet)'}.
Return ONLY a raw JSON array (no markdown fences, no prose) of up to 12 objects shaped exactly like:
{{"title": "...", "company": "...", "platform": "LinkedIn|Naukri|Indeed|Foundit|Instahyre|Cutshort|Other", "location": "...", "link": "https://...", "why": "one short sentence on why it matches"}}
If nothing new, return []."""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 1200,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    text = "\n".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
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

    jobs = call_claude(list(seen))
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
