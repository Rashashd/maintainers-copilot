import os
import random
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

REPO = "home-assistant/core"
BASE_URL = f"https://api.github.com/repos/{REPO}/issues"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"
}

PER_PAGE = 100
MAX_RETRIES = 5


def safe_request(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f"Connection error ({e}). Retrying in {wait:.1f}s...")
            time.sleep(wait)
            continue

        if resp.status_code == 403 and "X-RateLimit-Remaining" in resp.headers:
            reset_time = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_seconds = max(reset_time - int(time.time()), 30)
            print(f"Rate limit hit. Waiting {wait_seconds} seconds...")
            time.sleep(wait_seconds)
            continue

        if resp.status_code == 200:
            return resp

        if 500 <= resp.status_code < 600:
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f"Server error {resp.status_code}. Retrying in {wait:.1f}s...")
            time.sleep(wait)
            continue

        print(f"Error {resp.status_code}: {resp.text}")
        return None

    print("Max retries exceeded.")
    return None


def _next_url(link_header):
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            return part.split(";")[0].strip().strip("<>")
    return None


def fetch_issues():
    issues = {}
    url = f"{BASE_URL}?state=closed&per_page={PER_PAGE}&sort=created&direction=desc"

    while url:
        resp = safe_request(url)

        if resp is None:
            print("No data returned, stopping.")
            break

        data = resp.json()

        if isinstance(data, dict) and "message" in data:
            print(f"API error: {data}")
            break
        if not data:
            break

        for issue in data:
            if "pull_request" in issue:
                continue

            created_at = issue.get("created_at")
            if not created_at:
                continue

            labels = [lbl["name"].lower() for lbl in issue.get("labels", [])]

            if issue["id"] not in issues:
                issues[issue["id"]] = {
                    "id": issue["id"],
                    "title": issue.get("title", ""),
                    "body": issue.get("body") or "",
                    "labels": labels,
                    "created_at": created_at,
                    "closed_at": issue.get("closed_at"),
                }

        url = _next_url(resp.headers.get("Link"))
        print(f"Collected {len(issues)} labeled issues | {'more pages' if url else 'done'}")

    print(f"Total collected: {len(issues)} issues")
    return pd.DataFrame(list(issues.values()))


def main():
    df = fetch_issues()
    if df.empty:
        print("No issues collected. Check API token or repo path.")
        return

    os.makedirs("ml/data/raw", exist_ok=True)
    df.to_parquet("ml/data/raw/issues.parquet", index=False)
    print(f"Saved {len(df)} issues to ml/data/raw/issues.parquet")


if __name__ == "__main__":
    main()
