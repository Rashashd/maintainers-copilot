import re

_PARA_SEP = re.compile(r"\n{2,}")
_MAX_CHARS = 1800  # ~512 tokens at ~3.5 chars/token


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in _PARA_SEP.split(text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in parts:
        if current_len + len(para) > _MAX_CHARS and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text[:_MAX_CHARS]]


def chunk_issue(issue: dict) -> list[dict]:
    """
    Structural chunking:
    Body paragraphs become separate chunks (merged to stay under _MAX_CHARS).
    Each comment becomes its own chunk, prefixed with the issue title.
    """
    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    _comments_raw = issue.get("comments")
    comments: list[str] = list(_comments_raw) if _comments_raw is not None else []
    source_id = issue.get("url") or str(issue.get("number", ""))
    source_repo = issue.get("source_repo", "")

    base_meta = {
        "source_repo": source_repo,
        "issue_number": issue.get("number"),
        "created_at": str(issue.get("created_at", ""))[:10],
        "closed_at": str(issue.get("closed_at") or "")[:10] or None,
    }

    chunks: list[dict] = []

    # ── body chunks ───────────────────────────────────────────────────────────
    body_text = f"{title}\n\n{body}" if body else title
    for idx, para_chunk in enumerate(_split_paragraphs(body_text)):
        chunks.append({
            "source_type": "github_issue",
            "source_id": source_id,
            "title": title,
            "content": para_chunk,
            "chunk_index": idx,
            "metadata_": {**base_meta, "chunk_type": "body_paragraph", "comment_index": None},
        })

    body_count = len(chunks)

    # ── comment chunks ────────────────────────────────────────────────────────
    for c_idx, comment in enumerate(comments):
        if not comment or not comment.strip():
            continue
        content = f"{title}\n\n{comment.strip()}"
        chunks.append({
            "source_type": "github_issue",
            "source_id": source_id,
            "title": title,
            "content": content[:_MAX_CHARS],
            "chunk_index": body_count + c_idx,
            "metadata_": {**base_meta, "chunk_type": "comment", "comment_index": c_idx},
        })

    return chunks
