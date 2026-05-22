%%writefile /content/ATLAS/atlas/utils/load_cassia_data.py
"""
ATLAS data loader — uses CASSIA's example datasets.

Two loading strategies, tried in order:
  1. Local: if CASSIA is cloned next to ATLAS, read directly from disk
  2. Remote: download from CASSIA's GitHub raw URLs (cached locally)

This lets ATLAS work both in:
  - Dev environments where CASSIA is cloned (fast, offline)
  - Demo/web environments with only ATLAS (auto-downloads on first call)

Note: We don't commit CASSIA's data into ATLAS — it belongs to CASSIA's
repo. We just teach ATLAS how to find or fetch it.
"""

import os
from pathlib import Path
from typing import Optional, List
import pandas as pd


# Where CASSIA's data lives, in order of preference
_LOCAL_PATHS = [
    "/content/CASSIA/CASSIA_python/CASSIA/data",
    str(Path.home() / "CASSIA" / "CASSIA_python" / "CASSIA" / "data"),
]

# Fallback: download from CASSIA's GitHub
_REMOTE_BASE = (
    "https://raw.githubusercontent.com/ElliotXie/CASSIA/main/"
    "CASSIA_python/CASSIA/data"
)

# Where to cache remote downloads
_CACHE_DIR = Path.home() / ".atlas_cache" / "cassia_data"


def _resolve_file(filename: str) -> Path:
    """
    Find a data file, downloading if necessary.

    Tries local CASSIA clone first, then downloads from GitHub on miss.
    """
    # Check env override first
    env_dir = os.environ.get("CASSIA_DATA_DIR")
    candidates = [env_dir] + _LOCAL_PATHS if env_dir else _LOCAL_PATHS

    for cand in candidates:
        if not cand:
            continue
        p = Path(cand) / filename
        if p.is_file():
            return p

    # Local miss — try cache, then download
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = _CACHE_DIR / filename
    if cached.is_file():
        return cached

    url = f"{_REMOTE_BASE}/{filename}"
    print(f"📥 Downloading {filename} from CASSIA repo ({url})...")
    import urllib.request
    urllib.request.urlretrieve(url, cached)
    print(f"✅ Cached at {cached}")
    return cached


# ---------- Loaders ----------

def load_processed() -> pd.DataFrame:
    """Load processed.csv — one row per cluster with comma-separated markers."""
    path = _resolve_file("processed.csv")
    df = pd.read_csv(path)
    if df.columns[0] == "" or df.columns[0].startswith("Unnamed"):
        df = df.drop(columns=df.columns[0])
    df = df.rename(columns={
        "Broad.cell.type": "cluster_label",
        "Top.Markers": "markers",
    })
    return df.reset_index(drop=True)


def load_unprocessed() -> pd.DataFrame:
    """Load unprocessed.csv — full FindAllMarkers output."""
    path = _resolve_file("unprocessed.csv")
    df = pd.read_csv(path)
    if df.columns[0] == "" or df.columns[0].startswith("Unnamed"):
        df = df.drop(columns=df.columns[0])
    return df.reset_index(drop=True)


# ---------- Convenience helpers (unchanged from previous version) ----------

def get_marker_list_for_cluster(
    cluster_label: str,
    top_n: int = 50,
    processed_df: Optional[pd.DataFrame] = None,
) -> List[str]:
    if processed_df is None:
        processed_df = load_processed()
    matches = processed_df[processed_df["cluster_label"] == cluster_label]
    if len(matches) == 0:
        raise ValueError(
            f"Cluster label '{cluster_label}' not found. Available:\n"
            + "\n".join(f"  - {x}" for x in processed_df["cluster_label"].tolist())
        )
    raw = matches.iloc[0]["markers"]
    return [g.strip() for g in str(raw).split(",") if g.strip()][:top_n]


def get_findallmarkers_for_cluster(
    cluster_label: str,
    unprocessed_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    if unprocessed_df is None:
        unprocessed_df = load_unprocessed()
    sub = unprocessed_df[unprocessed_df["cluster"] == cluster_label].copy()
    if len(sub) == 0:
        raise ValueError(
            f"Cluster '{cluster_label}' not found. Available:\n"
            + "\n".join(f"  - {x}" for x in sorted(unprocessed_df['cluster'].unique()))
        )
    return sub.sort_values("avg_log2FC", ascending=False).reset_index(drop=True)


def list_available_clusters() -> List[str]:
    return load_processed()["cluster_label"].tolist()


if __name__ == "__main__":
    print("processed.csv clusters:", list_available_clusters())
