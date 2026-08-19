import json
import os
import re
import sys
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
STATE_FILE = "state.json"

PROFILE_ROLE = "ETL/QA Test Specialist"
PROFILE_YEARS = "9 yrs"
PROFILE_LOCATION = "India"
PROFILE_SKILLS = "SQL, PL/SQL, AWS(S3/Glue/Athena), Snowflake, PySpark, Airflow, Power BI, DWH, JIRA, STLC"
TITLES = "ETL Tester, QA Engineer-Data, DW Tester, Test Analyst-ETL, Data Quality Analyst, SDET-Data"
SITES = "LinkedIn, Naukri, Indeed India, Foundit, Instahyre, Cutshort"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"seen_links": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def call_claude(seen_links):
    skip = ", ".join(seen_links[-100:]) if seen_links else "none"
    prompt = (
        f"Find open jobs in {PROFILE_LOCATION}: {PROFILE_ROLE}, {PROFILE_YEARS}. "
        f"Skills: {PROFILE_SKILLS}. Titles like: {TITLES}. "
        f"Sites: {SITES}. Skip links: {skip}. "
        'Output ONLY a JSON array, max 10 items, no prose: '
        '[{"title":"","company":"","platform":"","location":"","link":"","why":""}] '
        '"why" max 12 words. Empty array if nothing new.'
    )

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 600,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
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
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"Claude API error {e.code}: {err_body}", file=sys.stderr)
        raise

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

    # ntfy title header must be ASCII-safe; percent-encode to survive
    # special characters in job titles/company names (ntfy decodes this).
    import urllib.parse
    safe_title = urllib.parse.quote(title)

    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": safe_title,
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

    print(f"Claude returned {len(jobs)} job(s) total, {len(new_jobs)} not already seen.")

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
