"""GitHub Issues integration (the team's task tracker).

.env:  GITHUB_TOKEN=...   GITHUB_REPO=owner/meeting-tasks
Swap this file to support Jira/Trello/Notion; nothing else needs to change.
"""
import os
import time

import requests

API = "https://api.github.com"


def _repo():
    repo = os.getenv("GITHUB_REPO")
    if not repo or not os.getenv("GITHUB_TOKEN"):
        raise RuntimeError("GitHub not configured: set GITHUB_TOKEN and GITHUB_REPO in .env")
    return repo


def _call(method, path, **kwargs):
    headers = {"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
               "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    for attempt in range(2):  # one retry on rate limit
        r = requests.request(method, f"{API}{path}", headers=headers, timeout=20, **kwargs)
        if r.status_code in (403, 429) and attempt == 0:
            time.sleep(int(r.headers.get("Retry-After", 5)))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub {r.status_code}: {r.json().get('message', r.text)[:200]}")
        return r.json()


def issue_body(task, owner, deadline, meeting_title, meeting_date, quote, speaker=None):
    return (f"**Owner:** {owner}\n**Due:** {deadline or 'not set'}\n"
            f"**From meeting:** {meeting_title} ({meeting_date})\n\n"
            f"> {quote}" + (f"\n> — {speaker}" if speaker else "") +
            "\n\n_Created by FollowThru after human approval._")


def create_issue(title, body, labels=("meeting-agent",)):
    """Returns (number, html_url)."""
    data = _call("POST", f"/repos/{_repo()}/issues", json={"title": title, "body": body, "labels": list(labels)})
    time.sleep(0.5)  # be gentle with GitHub's burst limits
    return data["number"], data["html_url"]


def comment(issue_number, body):
    return _call("POST", f"/repos/{_repo()}/issues/{issue_number}/comments", json={"body": body})["html_url"]


def add_labels(issue_number, labels):
    _call("POST", f"/repos/{_repo()}/issues/{issue_number}/labels", json={"labels": list(labels)})


def find_issue_by_title(title):
    """Returns (number, html_url) of an open issue with this exact title, or None."""
    for issue in _call("GET", f"/repos/{_repo()}/issues", params={"state": "open", "per_page": 100}):
        if issue["title"] == title:
            return issue["number"], issue["html_url"]
    return None


def list_open_issues(label="meeting-agent"):
    """Open issues with a label: [{'number', 'title', 'labels': [...]}]."""
    data = _call("GET", f"/repos/{_repo()}/issues", params={"state": "open", "labels": label, "per_page": 100})
    return [{"number": i["number"], "title": i["title"], "labels": [lb["name"] for lb in i.get("labels", [])]}
            for i in data if "pull_request" not in i]


def configured():
    return bool(os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPO"))


def close_issue(issue_number, reason="completed"):
    _call("PATCH", f"/repos/{_repo()}/issues/{issue_number}", json={"state": "closed", "state_reason": reason})
