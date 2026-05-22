"""
ATLAS data loader — uses the real CASSIA example datasets.

CASSIA ships three example files in CASSIA_python/CASSIA/data/:

  processed.csv      — one row per cluster, comma-separated top markers
                       (suitable for the default 4-agent pipeline)
  unprocessed.csv    — full FindAllMarkers output for each cluster
                       (suitable for the Annotation Boost ReAct loop)
  subcluster_results.csv — subcluster-level markers (subclustering agent)

Why use these instead of synthetic data:
  - Real biology, real noise — better stress test
  - Direct comparability with CASSIA paper results
  - Cluster 0 contains an intentional gold-standard error
    ("monocyte" labeled but markers are actually Schwann cell) —
    perfect for demonstrating ATLAS's Boost agent.

Assumes you've cloned CASSIA next to ATLAS, i.e.:
  /content/CASSIA/CASSIA_python/CASSIA/data/...
You can override the path with CASSIA_DATA_DIR env var.
"""

import os
from pathlib import Path
from typing import Optional, List, Tuple
import pandas as pd


# ---------- Locate the CASSIA data directory ----------

_DEFAULT_PATHS = [
    "/content/CASSIA/CASSIA_python/CASSIA/data",  # Colab + your setup
    str(Path.home() / "CASSIA" / "CASSIA_python" / "CASSIA" / "data"),
]


def find_cassia_data_dir() -> Path:
    """Find CASSIA's data directory. Returns a Path or raises."""
    env = os.environ.get("CASSIA_DATA_DIR")
    candidates = [env] + _DEFAULT_PATHS if env else _DEFAULT_PATHS
    for cand in candidates:
        if cand and Path(cand).is_dir():
            return Path(cand)
    raise FileNotFoundError(
        "Could not locate CASSIA data directory. Tried:\n  "
        + "\n  ".join(str(c) for c in candidates)
        + "\nClone CASSIA or set CASSIA_DATA_DIR environment variable."
    )


# ---------- Loaders ----------

def load_processed() -> pd.DataFrame:
    """
    Load the processed cluster summary (one row per cluster).

    Columns:
        Broad.cell.type — the gold-standard label (note: cluster 0 has an
                          intentional error, marked '(inaccurate annotation)')
        Top.Markers     — comma-separated gene symbols, top-N for that cluster

    Returns DataFrame indexed by row number with columns ['cluster_label', 'markers'].
    """
    path = find_cassia_data_dir() / "processed.csv"
    df = pd.read_csv(path)
    # The first column is just a row index ("1","2"...), drop it
    if df.columns[0] == "" or df.columns[0].startswith("Unnamed"):
        df = df.drop(columns=df.columns[0])
    df = df.rename(columns={
        "Broad.cell.type": "cluster_label",
        "Top.Markers": "markers",
    })
    return df.reset_index(drop=True)


def load_unprocessed() -> pd.DataFrame:
    """
    Load the full FindAllMarkers DataFrame for all clusters.

    Columns: gene, cluster, avg_log2FC, pct.1, pct.2, p_val, p_val_adj
    """
    path = find_cassia_data_dir() / "unprocessed.csv"
    df = pd.read_csv(path)
    # First column is a duplicate gene name (acts as row index in R) — drop it
    if df.columns[0] == "" or df.columns[0].startswith("Unnamed"):
        df = df.drop(columns=df.columns[0])
    return df.reset_index(drop=True)


# ---------- Convenience helpers ----------

def get_marker_list_for_cluster(
    cluster_label: str,
    top_n: int = 50,
    processed_df: Optional[pd.DataFrame] = None,
) -> List[str]:
    """
    Pull the top-N marker list for one cluster from processed.csv.

    Args:
        cluster_label: e.g. "plasma cell" or "monocyte (inaccurate annotation)".
        top_n: how many markers to take from the comma-separated string.
        processed_df: pre-loaded df (avoid re-reading); loads if None.

    Returns: list of gene symbols, ranked.
    """
    if processed_df is None:
        processed_df = load_processed()
    matches = processed_df[processed_df["cluster_label"] == cluster_label]
    if len(matches) == 0:
        avail = processed_df["cluster_label"].tolist()
        raise ValueError(
            f"Cluster label '{cluster_label}' not found. Available labels:\n"
            + "\n".join(f"  - {x}" for x in avail)
        )
    raw = matches.iloc[0]["markers"]
    genes = [g.strip() for g in str(raw).split(",") if g.strip()]
    return genes[:top_n]


def get_findallmarkers_for_cluster(
    cluster_label: str,
    unprocessed_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Pull the FULL FindAllMarkers DataFrame for one cluster (all rows, all stats).
    This is what Annotation Boost needs.

    Args:
        cluster_label: e.g. "plasma cell".
        unprocessed_df: pre-loaded df; loads if None.

    Returns: DataFrame with columns
             [gene, cluster, avg_log2FC, pct.1, pct.2, p_val, p_val_adj]
    """
    if unprocessed_df is None:
        unprocessed_df = load_unprocessed()
    sub = unprocessed_df[unprocessed_df["cluster"] == cluster_label].copy()
    if len(sub) == 0:
        avail = sorted(unprocessed_df["cluster"].unique())
        raise ValueError(
            f"Cluster '{cluster_label}' not found in unprocessed.csv. Available:\n"
            + "\n".join(f"  - {x}" for x in avail)
        )
    # Sort by descending log2FC (true marker ranking)
    sub = sub.sort_values("avg_log2FC", ascending=False).reset_index(drop=True)
    return sub


def list_available_clusters() -> List[str]:
    """List all cluster labels available in processed.csv."""
    df = load_processed()
    return df["cluster_label"].tolist()


# ---------- Self-test ----------

if __name__ == "__main__":
    print("CASSIA data dir:", find_cassia_data_dir())
    print()
    processed = load_processed()
    print(f"processed.csv: {len(processed)} clusters")
    for _, row in processed.iterrows():
        n_markers = len(str(row["markers"]).split(","))
        print(f"  - {row['cluster_label']!r}: {n_markers} markers")

    print()
    unprocessed = load_unprocessed()
    print(f"unprocessed.csv: {len(unprocessed)} rows total")
    print(f"  clusters: {sorted(unprocessed['cluster'].unique())}")
