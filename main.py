"""
Daily job-match + application-draft assistant for Sudip Kumar Adak.

What this does:
  1. Pulls fresh listings from RemoteOK, Arbeitnow, and (optionally) Adzuna — all
     legitimate public APIs, no scraping, no ToS violations.
  2. Filters listings against your skills/keywords in profile_config.py.
  3. Skips anything already seen (tracked in applied_log.csv).
  4. For each new match:
       - If the listing's description contains a direct contact email -> writes a
         personalized email straight into your Gmail Drafts folder (via IMAP).
       - Otherwise -> writes a personalized cover note + apply link to a .txt file
         in drafts/ for you to paste into the application portal.
  5. Logs everything to applied_log.csv so nothing repeats.

You run this yourself (manually, or via cron / Windows Task Scheduler) once a day.
Nothing sends automatically — you always review before hitting Send.

Setup:
  1. pip install -r requirements.txt
  2. Copy .env.example to .env and fill in your Gmail address + App Password
     (Google Account -> Security -> 2-Step Verification -> App Passwords).
     Optional: free Adzuna API keys from https://developer.adzuna.com/
  3. python main.py
"""

import os
import re
import csv
import smtplib
import imaplib
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from profile_config import PROFILE, SEARCH_KEYWORDS, EXCLUDE_KEYWORDS

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

LOG_FILE = "applied_log.csv"
DRAFTS_DIR = "drafts"
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Domains that show up in job descriptions but are never real HR contacts
EMAIL_BLOCKLIST_DOMAINS = {"example.com", "sentry.io", "wixpress.com", "schema.org"}

# Local-parts (the bit before @) that indicate a non-hiring contact even on the
# company's own domain — legal/privacy/security inboxes, not recruiters.
EMAIL_BLOCKLIST_PREFIXES = {
    "dpo", "privacy", "legal", "security", "abuse", "compliance", "press",
    "media", "support", "billing", "sales", "info", "webmaster", "noreply",
    "no-reply", "admin", "postmaster",
}

# Only trust an extracted email if it appears near one of these cue words,
# to avoid grabbing an unrelated address from boilerplate/footer text.
HIRING_CUE_WORDS = ["apply", "send your resume", "send your cv", "send resume",
                    "send cv", "email us", "reach out to", "contact us at",
                    "careers@", "jobs@", "hr@", "recruit"]


# --------------------------------------------------------------------------- #
# Job sources
# --------------------------------------------------------------------------- #

def fetch_remoteok():
    """RemoteOK public API — free, no key required."""
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[RemoteOK] fetch failed: {e}")
        return []

    jobs = []
    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue
        jobs.append({
            "source": "RemoteOK",
            "title": item.get("position", ""),
            "company": item.get("company", ""),
            "description": item.get("description", "") or "",
            "url": item.get("url", "") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}",
            "id": f"remoteok-{item.get('id', item.get('url', ''))}",
        })
    return jobs


def fetch_arbeitnow():
    """Arbeitnow public job board API — free, no key required."""
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=15)
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as e:
        print(f"[Arbeitnow] fetch failed: {e}")
        return []

    jobs = []
    for item in data:
        jobs.append({
            "source": "Arbeitnow",
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "description": item.get("description", "") or "",
            "url": item.get("url", ""),
            "id": f"arbeitnow-{item.get('slug', item.get('url', ''))}",
        })
    return jobs


def fetch_adzuna():
    """Adzuna India listings — requires free API keys (developer.adzuna.com). Skipped if not set."""
    if not (ADZUNA_APP_ID and ADZUNA_APP_KEY):
        print("[Adzuna] Skipped (no ADZUNA_APP_ID / ADZUNA_APP_KEY in .env)")
        return []

    jobs = []
    for kw in SEARCH_KEYWORDS[:5]:  # keep API usage modest
        try:
            r = requests.get(
                "https://api.adzuna.com/v1/api/jobs/in/search/1",
                params={
                    "app_id": ADZUNA_APP_ID,
                    "app_key": ADZUNA_APP_KEY,
                    "what": kw,
                    "results_per_page": 10,
                    "content-type": "application/json",
                },
                timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
        except Exception as e:
            print(f"[Adzuna] fetch failed for '{kw}': {e}")
            continue

        for item in results:
            jobs.append({
                "source": "Adzuna",
                "title": item.get("title", ""),
                "company": (item.get("company") or {}).get("display_name", ""),
                "description": item.get("description", "") or "",
                "url": item.get("redirect_url", ""),
                "id": f"adzuna-{item.get('id', item.get('redirect_url',''))}",
            })
    return jobs


# --------------------------------------------------------------------------- #
# Matching + dedup
# --------------------------------------------------------------------------- #

def matches_profile(job):
    title = (job['title'] or "").lower()
    text = f"{title} {job['description']}".lower()
    if any(bad in text for bad in EXCLUDE_KEYWORDS):
        return False
    # Require the exact keyword phrase to appear (in title OR description) —
    # no more loose "all words present somewhere" matching, which was pulling
    # in unrelated titles like "Business Analyst" via stray word overlap.
    return any(kw.lower() in text for kw in SEARCH_KEYWORDS)


def load_seen_ids():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, newline="", encoding="utf-8") as f:
        return {row["job_id"] for row in csv.DictReader(f)}


def log_result(job, action, extra=""):
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "source", "job_id", "title", "company", "url", "action", "notes"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": job["source"],
            "job_id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "url": job["url"],
            "action": action,
            "notes": extra,
        })


def total_applications_count():
    if not os.path.exists(LOG_FILE):
        return 0
    with open(LOG_FILE, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


# --------------------------------------------------------------------------- #
# Drafting
# --------------------------------------------------------------------------- #

def find_contact_email(description):
    text = description or ""
    text_lower = text.lower()
    has_hiring_cue = any(cue in text_lower for cue in HIRING_CUE_WORDS)

    for m in EMAIL_REGEX.findall(text):
        domain = m.split("@")[-1].lower()
        local_part = m.split("@")[0].lower()
        if domain in EMAIL_BLOCKLIST_DOMAINS:
            continue
        if local_part in EMAIL_BLOCKLIST_PREFIXES:
            continue
        # Require an explicit hiring cue somewhere in the text before we trust
        # any extracted email — otherwise it's likely a footer/legal contact.
        if not has_hiring_cue:
            continue
        return m
    return None


def compose_application(job):
    p = PROFILE
    role_hint = job["title"] or "the role"
    company = job["company"] or "your team"

    subject = f"Application for {role_hint} — {p['name']}"

    body = f"""Dear Hiring Team at {company},

I'm writing to apply for the {role_hint} position. I'm {p['name']}, an MCA student ({p['education']}) \
based in {p['location']}, with hands-on experience in {', '.join(p['skills'][:6])}.

Most recently I built {p['flagship_project']['name']} — {p['flagship_project']['desc']}. \
You can see it live here: {p['flagship_project']['link']}. I've also worked on {p['other_projects'][0]} \
and {p['other_projects'][1]}.

I'd welcome the chance to bring that same hands-on, full-stack + AI/ML background to {company}. \
My portfolio, resume details, and other projects are here: {p['portfolio']} \
GitHub: {p['github']} | LinkedIn: {p['linkedin']}

Thank you for your time and consideration — I'd love to talk further.

Best regards,
{p['name']}
{p['email']}
"""
    return subject, body


def save_gmail_draft(to_addr, subject, body):
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD):
        print("  -> Gmail credentials not set in .env; skipping draft save.")
        return False

    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.attach(MIMEText(body, "plain"))

    resume_path = PROFILE.get("resume_path", "")
    if resume_path and os.path.exists(resume_path):
        from email.mime.application import MIMEApplication
        with open(resume_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(resume_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(resume_path)}"'
        msg.attach(part)

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        imap.append('"[Gmail]/Drafts"', "", imaplib.Time2Internaldate(datetime.now().timestamp()),
                    msg.as_bytes())
        imap.logout()
        return True
    except Exception as e:
        print(f"  -> Failed to save Gmail draft: {e}")
        return False


def save_text_draft(job, subject, body):
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    safe_company = re.sub(r"[^\w\-]+", "_", job["company"] or "company")[:40]
    safe_title = re.sub(r"[^\w\-]+", "_", job["title"] or "role")[:40]
    fname = f"{DRAFTS_DIR}/{safe_company}_{safe_title}.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"Job: {job['title']} @ {job['company']}\n")
        f.write(f"Apply here: {job['url']}\n")
        f.write(f"Source: {job['source']}\n\n")
        f.write(f"Subject: {subject}\n\n")
        f.write(body)
    return fname


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def write_dashboard_json(total_fetched, total_matched, todays_entries, ran_ok=True, error_msg=""):
    """Writes the public-safe summary file the portfolio dashboard reads.
    Merges today's new entries (which include full draft text so it survives
    even though the GitHub Actions runner itself is thrown away after each run)
    with whatever was already in dashboard_data.json from previous days."""
    import json

    previous_recent = []
    if os.path.exists("dashboard_data.json"):
        try:
            with open("dashboard_data.json", encoding="utf-8") as f:
                previous_recent = json.load(f).get("recent_matches", [])
        except Exception:
            previous_recent = []

    combined = (todays_entries + previous_recent)[:20]

    summary = {
        "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ran_ok": ran_ok,
        "error": error_msg,
        "total_fetched_today": total_fetched,
        "total_new_matches_today": total_matched,
        "total_applications_all_time": total_applications_count(),
        "recent_matches": combined,
    }
    with open("dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def main():
    print("Fetching listings...")
    all_jobs = fetch_remoteok() + fetch_arbeitnow() + fetch_adzuna()
    print(f"Fetched {len(all_jobs)} total listings.")

    seen = load_seen_ids()
    matched = [j for j in all_jobs if j["id"] not in seen and matches_profile(j)]
    print(f"{len(matched)} new matching listings found.\n")

    if not matched:
        print("No new matches today. Run again tomorrow!")
        write_dashboard_json(len(all_jobs), 0, [])
        return

    todays_entries = []

    for job in matched:
        print(f"- {job['title']} @ {job['company']} ({job['source']})")
        subject, body = compose_application(job)
        contact_email = find_contact_email(job["description"])
        entry = {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": job["source"],
            "title": job["title"],
            "company": job["company"],
            "url": job["url"],
            "subject": subject,
        }

        if contact_email:
            ok = save_gmail_draft(contact_email, subject, body)
            if ok:
                print(f"  -> Draft saved in Gmail, addressed to {contact_email}")
                log_result(job, "gmail_draft", contact_email)
                entry["action"] = "gmail_draft"
                entry["contact_email"] = contact_email
            else:
                save_text_draft(job, subject, body)  # local-only convenience copy
                log_result(job, "text_draft_fallback", contact_email)
                entry["action"] = "text_draft"
                entry["draft_body"] = body
        else:
            save_text_draft(job, subject, body)  # local-only convenience copy
            print(f"  -> No direct email found; drafted pitch text (see dashboard)")
            log_result(job, "text_draft", "")
            entry["action"] = "text_draft"
            entry["draft_body"] = body

        todays_entries.append(entry)

    print(f"\nDone. Check your Gmail Drafts folder and the dashboard for text drafts.")
    print(f"Full history logged in {LOG_FILE}.")
    write_dashboard_json(len(all_jobs), len(matched), todays_entries)


if __name__ == "__main__":
    main()
