import pandas as pd

# Maps home-assistant raw label names → one of: bug | feature | docs | question
# Extend this dict if new label variants appear after inspecting raw data.
LABEL_MAP = {
    # bug
    "bug": "bug",
    "type: bug": "bug",
    "confirmed bug": "bug",
    "regression": "bug",
    "problem in dependency": "bug",
    "problem in device": "bug",
    "problem in custom integration": "bug",
    "problem in config": "bug",
    "problem with file system": "bug",
    "problem in database": "bug",
    "problem in platform": "bug",
    "config error": "bug",
    # feature
    "enhancement": "feature",
    "feature_request": "feature",
    "feature request": "feature",
    "feature-request": "feature",
    "type: feature": "feature",
    "type: feature-request": "feature",
    "new-integration": "feature",
    "new-feature": "feature",
    # docs
    "docs": "docs",
    "documentation": "docs",
    "docs-missing": "docs",
    "type: docs": "docs",
    "type: documentation": "docs",
    # question
    "question": "question",
    "usage question": "question",
    "type: question": "question",
    "support": "question",
    "help wanted": "question",
    "help-wanted": "question",
}


def map_labels(labels: list[str]) -> str | None:
    """Return the first mapped class for a list of raw labels, or None."""
    for label in labels:
        if label in LABEL_MAP:
            return LABEL_MAP[label]
    return None


def apply(df: pd.DataFrame) -> pd.DataFrame:
    """Add mapped_label column and drop issues that don't match any class."""
    df = df.copy()
    df["mapped_label"] = df["labels"].apply(map_labels)
    dropped = df["mapped_label"].isna().sum()
    df = df.dropna(subset=["mapped_label"]).reset_index(drop=True)
    print(f"Mapped {len(df)} issues | Dropped {dropped} with no matching label")
    return df
