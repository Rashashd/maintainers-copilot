import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import label_map


def split_dataset(df):
    df["created_at"] = pd.to_datetime(df["created_at"])

    train_parts: list[pd.DataFrame] = []
    val_parts:   list[pd.DataFrame] = []
    test_parts:  list[pd.DataFrame] = []
    for _, group in df.groupby("mapped_label"):
        group = group.sort_values("created_at")
        n = len(group)
        train_end = int(0.70 * n)
        val_end   = int(0.85 * n)
        train_parts.append(group.iloc[:train_end])
        val_parts.append(group.iloc[train_end:val_end])
        test_parts.append(group.iloc[val_end:])

    train = pd.concat(train_parts).sort_values("created_at").reset_index(drop=True)
    val   = pd.concat(val_parts).sort_values("created_at").reset_index(drop=True)
    test  = pd.concat(test_parts).sort_values("created_at").reset_index(drop=True)
    return train, val, test


def main():
    df = pd.read_parquet("ml/data/raw/issues.parquet")

    docs_path = "ml/data/raw/docs_issues.parquet"
    if os.path.exists(docs_path):
        df_docs = pd.read_parquet(docs_path)
        df = pd.concat([df, df_docs], ignore_index=True).drop_duplicates(subset=["id"])
        print(f"Merged docs issues: {len(df_docs)} added")

    df = label_map.apply(df)
    train, val, test = split_dataset(df)

    os.makedirs("ml/data/splits", exist_ok=True)
    train.to_parquet("ml/data/splits/train.parquet", index=False)
    val.to_parquet("ml/data/splits/val.parquet", index=False)
    test.to_parquet("ml/data/splits/test.parquet", index=False)

    print(f"Splits saved — train: {len(train)}, val: {len(val)}, test: {len(test)}")
    for name, split in [("train", train), ("val", val), ("test", test)]:
        dist = split["mapped_label"].value_counts(normalize=True).round(3).to_dict()
        print(f"  {name}: {dist}")


if __name__ == "__main__":
    main()