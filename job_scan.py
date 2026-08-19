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

# Guaranteed-valid fallback search links per platform, used when Claude can't
# surface a specific posting URL (common -- LinkedIn/Naukri mostly index
# aggregate listing pages, not individual postings, for outside search).
FALLBACK_LINKS = {
    "LinkedIn": "https://www.linkedin.com/jobs/search/?keywords=ETL%20Tester&location=India",
    "Naukri": "https://www.naukri.com/etl-tester-jobs-in-india",
    "Indeed": "https://in.indeed.com/jobs?q=ETL+Tester&l=India",
    "Foundit": "https://www.foundit.in/srp/results?query=ETL%20Tester&locations=India",
    "Instahyre": "https://www.instahyre.com/search-jobs/?q=ETL%20Tester",
    "Cutshort": "https://cutshort.io/jobs?q=ETL%20Tester",
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"seen_links": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def call_claude(seen_keys):
    skip = ", ".join(seen_keys[-100:]) if seen_keys else "none"
    prompt = (
        f"Find open jobs in {PROFILE_LOCATION}: {PROFILE_ROLE}, {PROFILE_YEARS}. "
        f"Skills: {PROFILE_SKILLS}. Titles like: {TITLES}. "
        f"Search each site: {SITES}. Use site-specific queries (e.g. site:naukri.com) "
        f"to try to find individual posting pages, not just category/listing pages. "
        f"Skip already-notified (title@company): {skip}. "
        'Output ONLY a JSON array, max 10 items, no prose: '
        '[{"title":"","company":"","platform":"","location":"","link":"","why":""}] '
        'If you find a specific posting URL use it; if you can only confirm a role type '
        'exists via an aggregate/category page, still include the item and set "link" to '
        'that category page URL. "why" max 12 words. Empty array only if truly nothing relevant.'
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

    block_types = [b.get("type") for b in data.get("content", [])]
    print(f"Response block types: {block_types}", file=sys.stderr)
    print(f"Stop reason: {data.get('stop_reason')}", file=sys.stderr)

    text = "\n".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    print(f"--- Raw Claude text (first 500 chars) ---\n{text[:500]}\n--- end ---", file=sys.stderr)
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


def notify_no_jobs(total_found):
    message = (
        f"Scanned platforms — {total_found} job(s) seen, all already notified."
        if total_found
        else "Scanned platforms — no matching jobs found this run."
    )
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "Job scan complete",
            "Priority": "low",
            "Tags": "mag",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30)


def main():
    state = load_state()
    seen = set(state.get("seen_keys", state.get("seen_links", [])))  # migrate old state if present

    jobs = call_claude(list(seen))
    print(f"Response contains {len(jobs)} raw job(s) from Claude.")

    new_jobs = []
    for j in jobs:
        if not j.get("title") or not j.get("company"):
            continue
        key = f"{j['title']} @ {j['company']}"
        if key in seen:
            continue
        if not j.get("link"):
            j["link"] = FALLBACK_LINKS.get(j.get("platform", ""), "")
        new_jobs.append(j)

    print(f"{len(new_jobs)} job(s) not already seen.")

    for job in new_jobs:
        try:
            notify(job)
            seen.add(f"{job['title']} @ {job['company']}")
        except Exception as e:
            print(f"Failed to notify for {job.get('title')}: {e}", file=sys.stderr)

    if not new_jobs:
        try:
            notify_no_jobs(len(jobs))
        except Exception as e:
            print(f"Failed to send no-jobs notification: {e}", file=sys.stderr)

    state["seen_keys"] = list(seen)[-500:]  # cap growth
    state.pop("seen_links", None)  # drop old key name
    save_state(state)
    print(f"Scan complete. {len(new_jobs)} new job(s) pushed.")


if __name__ == "__main__":
    main()
