from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {"entity_type", "entity_name", "entity_id", "include", "team"}
OPTIONAL_COLUMNS = ["png", "gender", "height"]


def load_selection_csv(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [str(col).strip().lower() for col in df.columns]
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Selection CSV is missing columns: {sorted(missing)}")

    cleaned = df.copy()
    cleaned["entity_type"] = cleaned["entity_type"].astype(str).str.strip().str.lower()
    cleaned["entity_name"] = cleaned["entity_name"].astype(str).str.strip()
    cleaned["entity_id"] = cleaned["entity_id"].astype(str).str.strip()
    cleaned["team"] = cleaned["team"].astype(str).str.strip()
    cleaned["include"] = (
        cleaned["include"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )

    for column in OPTIONAL_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = pd.NA

    cleaned = cleaned[cleaned["include"]].copy()

    valid_types = {"team", "person"}
    invalid_types = sorted(set(cleaned["entity_type"]).difference(valid_types))
    if invalid_types:
        raise ValueError(f"Unsupported entity_type values: {invalid_types}")

    return cleaned.reset_index(drop=True)


def split_selected_entities(
    selection_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        selection_df[selection_df["entity_type"] == "team"].copy(),
        selection_df[selection_df["entity_type"] == "person"].copy(),
    )
