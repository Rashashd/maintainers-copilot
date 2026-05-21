"""
Fetch the RAG corpus from GitHub — run once to bootstrap the knowledge base.

Sources:
  1. home-assistant/core  — closed issues WITH maintainer comments,
                            skipping IDs already in classifier splits
  2. home-assistant/home-assistant.io — closed issues NOT already fetched
                            by ml/data/fetch_docs.py (docs_issues.parquet)

Two separate exclusion sets prevent data leakage from each source:
  - core_excluded  : train/val/test split IDs  (classifier training data)
  - docs_excluded  : docs_issues.parquet IDs   (classifier docs augmentation)

Output: /rag_corpus.parquet
Columns: id, number, title, body, comments (list[str]), url,
         source_repo, created_at, closed_at
"""

import os
import random
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

CORE_REPO = "home-assistant/core"
DOCS_REPO = "home-assistant/home-assistant.io"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
}

PER_PAGE               = 100
MAX_RETRIES            = 5
MAX_CORE_ISSUES        = 3000
MAX_DOCS_ISSUES        = 1000
MAX_COMMENTS_PER_ISSUE = 3
SPLITS_DIR             = "ml/data/splits"
DOCS_ISSUES_PATH       = "ml/data/raw/docs_issues.parquet"
OUTPUT_PATH            = "app/rag/data/rag_corpus.parquet"


# HTTP helper

def safe_request(url: str) -> requests.Response | None:
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
            print(f"Rate limit hit. Waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
            continue

        if resp.status_code == 200:
            return resp

        if 500 <= resp.status_code < 600:
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f"Server error {resp.status_code}. Retrying in {wait:.1f}s...")
            time.sleep(wait)
            continue

        print(f"Error {resp.status_code}: {resp.text[:200]}")
        return None

    print("Max retries exceeded.")
    return None


def _next_url(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            return part.split(";")[0].strip().strip("<>")
    return None


# Exclusion sets

def load_core_excluded() -> set[int]:
    """IDs from classifier train/val/test — must not appear in core RAG issues."""
    ids: set[int] = set()
    missing = []
    for fname in ("train.parquet", "val.parquet", "test.parquet"):
        path = os.path.join(SPLITS_DIR, fname)
        if os.path.exists(path):
            df = pd.read_parquet(path, columns=["id"])
            ids.update(df["id"].tolist())
        else:
            missing.append(fname)
    if missing:
        raise FileNotFoundError(
            f"Classifier splits not found: {missing}. "
            "Run ml/data/split.py before fetching the RAG corpus."
        )
    print(f"core_excluded: {len(ids):,} classifier split IDs")
    return ids


def load_docs_excluded() -> set[int]:
    """IDs from docs_issues.parquet — .io issues already used for classifier training."""
    if not os.path.exists(DOCS_ISSUES_PATH):
        raise FileNotFoundError(
            f"{DOCS_ISSUES_PATH} not found. "
            "Run ml/data/fetch_docs.py before fetching the RAG corpus."
        )
    df = pd.read_parquet(DOCS_ISSUES_PATH, columns=["id"])
    ids = set(df["id"].tolist())
    print(f"docs_excluded: {len(ids):,} IDs from docs_issues.parquet")
    return ids


# Fetch comments for a single issue

def fetch_comments(repo: str, issue_number: int, max_comments: int) -> list[str]:
    url = (
        f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
        f"?per_page={max_comments}"
    )
    resp = safe_request(url)
    if resp is None:
        return []
    data = resp.json()
    if not isinstance(data, list):
        return []
    return [c.get("body", "") for c in data[:max_comments] if c.get("body")]


# Fetch core issues (with maintainer comments)

def fetch_core_issues(excluded: set[int], max_issues: int = MAX_CORE_ISSUES) -> list[dict]:
    issues: list[dict] = []
    url = (
        f"https://api.github.com/repos/{CORE_REPO}/issues"
        f"?state=closed&per_page={PER_PAGE}&sort=created&direction=desc"
    )

    while url and len(issues) < max_issues:
        resp = safe_request(url)
        if resp is None:
            break

        data = resp.json()
        if isinstance(data, dict) and "message" in data:
            print(f"API error: {data}")
            break
        if not data:
            break

        for issue in data:
            if len(issues) >= max_issues:
                break
            if "pull_request" in issue:
                continue
            if issue.get("comments", 0) == 0:
                continue
            if issue["id"] in excluded:
                continue
            if not issue.get("created_at"):
                continue

            comments = fetch_comments(CORE_REPO, issue["number"], MAX_COMMENTS_PER_ISSUE)
            if not comments:
                continue

            issues.append({
                "id":          issue["id"],
                "number":      issue["number"],
                "title":       issue.get("title", ""),
                "body":        issue.get("body") or "",
                "comments":    comments,
                "url":         issue.get("html_url", ""),
                "source_repo": CORE_REPO,
                "created_at":  issue["created_at"],
                "closed_at":   issue.get("closed_at"),
            })

            if len(issues) % 100 == 0:
                print(f"  [core] {len(issues)} issues collected...")

        url = _next_url(resp.headers.get("Link"))

    print(f"Core issues collected: {len(issues)}")
    return issues


# Fetch docs issues (home-assistant.io) ─────────────────────────────────────

def fetch_docs_issues(excluded: set[int], max_issues: int = MAX_DOCS_ISSUES) -> list[dict]:
    issues: list[dict] = []
    url = (
        f"https://api.github.com/repos/{DOCS_REPO}/issues"
        f"?state=closed&per_page={PER_PAGE}&sort=created&direction=desc"
    )

    while url and len(issues) < max_issues:
        resp = safe_request(url)
        if resp is None:
            break

        data = resp.json()
        if isinstance(data, dict) and "message" in data:
            print(f"API error: {data}")
            break
        if not data:
            break

        for issue in data:
            if len(issues) >= max_issues:
                break
            if "pull_request" in issue:
                continue
            if issue["id"] in excluded:
                continue
            if not issue.get("created_at"):
                continue

            issues.append({
                "id":          issue["id"],
                "number":      issue["number"],
                "title":       issue.get("title", ""),
                "body":        issue.get("body") or "",
                "comments":    [],
                "url":         issue.get("html_url", ""),
                "source_repo": DOCS_REPO,
                "created_at":  issue["created_at"],
                "closed_at":   issue.get("closed_at"),
            })

            if len(issues) % 100 == 0:
                print(f"  [docs] {len(issues)} issues collected...")

        url = _next_url(resp.headers.get("Link"))

    print(f"Docs issues collected: {len(issues)}")
    return issues


# Entry point

def main():
    core_excluded = load_core_excluded()
    docs_excluded = load_docs_excluded()

    print(f"\nFetching core issues (max {MAX_CORE_ISSUES}, skipping {len(core_excluded):,} split IDs)...")
    core = fetch_core_issues(core_excluded)

    print(f"\nFetching .io docs issues (max {MAX_DOCS_ISSUES}, skipping {len(docs_excluded):,} already-used IDs)...")
    docs = fetch_docs_issues(docs_excluded)

    df = pd.DataFrame(core + docs)
    if df.empty:
        print("No issues collected. Check your GITHUB_TOKEN.")
        return

    df = df.drop_duplicates(subset=["id"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)

    print(f"\nSaved {len(df):,} RAG corpus entries to {OUTPUT_PATH}")
    print(f"  core: {len(core):,}  docs: {len(docs):,}")
    print(f"  columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
