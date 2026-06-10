#!/usr/bin/env python3
"""Assign all open issues in ediminator/homematicip-hcu to Phil7989."""

import os
import sys
import json
import urllib.request
import urllib.error

OWNER = "ediminator"
REPO = "homematicip-hcu"
ASSIGNEE = "Phil7989"
API_BASE = "https://api.github.com"


def github_request(method: str, path: str, data: dict | None = None) -> dict | list:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)

    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_all_open_issues() -> list[dict]:
    issues = []
    page = 1
    while True:
        path = f"/repos/{OWNER}/{REPO}/issues?state=open&per_page=100&page={page}"
        batch = github_request("GET", path)
        if not batch:
            break
        # Filter out pull requests (GitHub API returns PRs in /issues)
        issues.extend(item for item in batch if "pull_request" not in item)
        if len(batch) < 100:
            break
        page += 1
    return issues


def assign_issue(issue_number: int) -> None:
    path = f"/repos/{OWNER}/{REPO}/issues/{issue_number}/assignees"
    github_request("POST", path, {"assignees": [ASSIGNEE]})


def main() -> None:
    print(f"Fetching all open issues for {OWNER}/{REPO} ...")
    issues = get_all_open_issues()
    print(f"Found {len(issues)} open issue(s).")

    for issue in issues:
        number = issue["number"]
        title = issue["title"]
        current = [a["login"] for a in issue.get("assignees", [])]
        if ASSIGNEE in current:
            print(f"  #{number} already assigned — skipping: {title}")
            continue
        print(f"  #{number} assigning ... {title}")
        assign_issue(number)

    print("Done.")


if __name__ == "__main__":
    main()
