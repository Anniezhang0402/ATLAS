"""
⚠️ DEPRECATED — Prefer atlas.utils.load_cassia_data
======================================================
This synthetic FindAllMarkers generator was used during early ATLAS
development. It still works, but the real CASSIA example data is a
better testbed:

  from atlas.utils.load_cassia_data import load_unprocessed
  df = load_unprocessed()

Kept for reference and as a fallback when CASSIA isn't cloned locally.
======================================================
"""

"""
ATLAS Mock Data Generator
=========================
Builds a realistic FindAllMarkers-style CSV with 4 clusters designed to
exercise the Annotation Boost pipeline:

  Cluster 0: Clean CD8+ T cell  — high score, no boost needed
  Cluster 1: Plasma cell with HOUSEKEEPING markers ranked top —
             top 10 looks like "generic cell", IGHG/IGKC buried at ranks 20-30.
             Boost should dig deeper and find plasma identity.
  Cluster 2: Proximal tubule cell mimicking the paper's Fig.5d example —
             top markers look hepatocyte-like (ALB-similar profile).
             Boost should detect tissue mismatch.
  Cluster 3: Mixed T+B cell — equal markers from both. Boost should flag.

Columns match what Seurat's FindAllMarkers produces:
  gene, cluster, avg_log2FC, pct.1, pct.2, p_val, p_val_adj
"""

import numpy as np
import pandas as pd
from pathlib import Path


# Canonical marker panels — ordered roughly by specificity/strength
_CD8_TCELL = [
    "CD8A", "CD8B", "CD3D", "CD3E", "CD3G", "GZMK", "GZMA", "NKG7", "CCL5",
    "CST7", "IL7R", "CD2", "LCK", "PRF1", "TRAC", "TRBC1", "TRBC2", "GNLY",
    "EOMES", "RUNX3", "ZAP70", "KLRG1", "FYN", "ITK",
]

_PLASMA_TRUE = [
    "IGHG1", "IGHG3", "IGHG4", "IGKC", "IGLC2", "IGLC3", "MZB1", "JCHAIN",
    "XBP1", "PRDM1", "IRF4", "TNFRSF17", "CD38", "CD27", "DERL3", "SDC1",
    "FKBP11", "MANF", "SSR4", "HERPUD1", "SEC11C",
]

# Housekeeping genes that "drown out" the real plasma signal in cluster 1
_HOUSEKEEPING = [
    "GAPDH", "ACTB", "B2M", "HSP90AA1", "HSP90AB1", "HSPA8", "EEF1A1",
    "PPIA", "PFN1", "TPT1", "UBA52", "FAU",
]

_HEPATOCYTE_LIKE = [
    # These overlap with proximal tubule "absorptive epithelium" signature
    "ALB", "TTR", "APOA1", "APOA2", "APOC3", "TF", "HP", "FABP1", "SERPINA1",
    "AHSG", "FGB", "FGA",
]

_PROXIMAL_TUBULE_TRUE = [
    "SLC34A1", "SLC22A12", "KAP", "CUBN", "LRP2", "SLC13A3", "SLC22A6",
    "SLC22A8", "GGT1", "AQP1", "PDZK1", "MIOX",
]

_B_CELL = [
    "MS4A1", "CD79A", "CD79B", "CD19", "IGHM", "IGHD", "BANK1", "CD22",
    "BLNK", "CXCR5", "TCL1A", "FCER2",
]

# A pool of random background genes for noise / pct.2
_BACKGROUND = [
    "MALAT1", "NEAT1", "FOS", "JUN", "JUNB", "EGR1", "NFKBIA", "DUSP1",
    "ZFP36", "BTG1", "BTG2", "RHOB", "TXNIP", "KLF2", "KLF6", "TSC22D3",
    "SAT1", "LDHA", "ENO1", "PGK1", "S100A4", "S100A6", "S100A10", "S100A11",
    "VIM", "TMSB4X", "TMSB10", "FTH1", "FTL", "CD52", "CXCR4", "CD74",
]


def _make_cluster_rows(cluster_id, ordered_markers, n_filler=70,
                       fc_top=4.0, fc_decay=0.04):
    """
    Generate one cluster's worth of rows.

    Top markers get high log2FC; tail markers get smaller (still positive) FC.
    Background-filler markers added to reach ~100 genes total per cluster.
    """
    rng = np.random.default_rng(seed=cluster_id * 13 + 7)
    rows = []
    seen = set()

    # 1. The "ranked" specific markers — strong, decreasing FC
    for rank, gene in enumerate(ordered_markers):
        if gene in seen:
            continue
        seen.add(gene)
        fc = max(0.6, fc_top - rank * fc_decay - rng.uniform(0, 0.15))
        pct1 = float(np.clip(0.95 - rank * 0.005 - rng.uniform(0, 0.05), 0.5, 0.99))
        pct2 = float(np.clip(rng.uniform(0.05, 0.25), 0.01, 0.5))
        pval = float(10 ** (-(rng.uniform(20, 200))))  # tiny p-values
        rows.append({
            "gene": gene,
            "cluster": cluster_id,
            "avg_log2FC": round(fc, 3),
            "pct.1": round(pct1, 3),
            "pct.2": round(pct2, 3),
            "p_val": pval,
            "p_val_adj": min(pval * 20000, 1.0),  # rough multi-test correction
        })

    # 2. Background filler — small positive FC, modest sig
    rng.shuffle(_BACKGROUND)
    for gene in _BACKGROUND[:n_filler]:
        if gene in seen:
            continue
        seen.add(gene)
        fc = float(rng.uniform(0.3, 1.0))
        pct1 = float(rng.uniform(0.3, 0.7))
        pct2 = float(rng.uniform(0.2, 0.6))
        pval = float(10 ** (-rng.uniform(2, 10)))
        rows.append({
            "gene": gene,
            "cluster": cluster_id,
            "avg_log2FC": round(fc, 3),
            "pct.1": round(pct1, 3),
            "pct.2": round(pct2, 3),
            "p_val": pval,
            "p_val_adj": min(pval * 20000, 1.0),
        })

    # Sort by descending log2FC so 'rank' = row order = top-of-list
    rows.sort(key=lambda r: -r["avg_log2FC"])
    return rows


def build_mock_findallmarkers(output_path: str = None) -> pd.DataFrame:
    """
    Build a 4-cluster mock FindAllMarkers DataFrame.

    Args:
        output_path: If provided, also save as CSV here.

    Returns:
        DataFrame with columns: gene, cluster, avg_log2FC, pct.1, pct.2,
                                p_val, p_val_adj
    """
    all_rows = []

    # Cluster 0: Clean CD8+ T cell — strong signal on top, easy case
    all_rows.extend(_make_cluster_rows(0, _CD8_TCELL, n_filler=70, fc_top=5.0))

    # Cluster 1: Plasma cell, but housekeeping ranked first (THE TRAP)
    # We deliberately put housekeeping markers at the TOP of the ranked list
    # with higher log2FC, so a marker-list-only annotator sees mostly noise.
    trap_order = _HOUSEKEEPING + _PLASMA_TRUE  # housekeeping first!
    all_rows.extend(_make_cluster_rows(1, trap_order, n_filler=65, fc_top=4.0))

    # Cluster 2: Proximal tubule — hepatocyte-like top markers
    # ALB-family at top fools generic annotators into thinking 'hepatocyte'
    trap2_order = _HEPATOCYTE_LIKE + _PROXIMAL_TUBULE_TRUE
    all_rows.extend(_make_cluster_rows(2, trap2_order, n_filler=70, fc_top=4.5))

    # Cluster 3: Mixed T + B (50:50)
    # Interleave so neither dominates top of list
    interleaved = []
    for t, b in zip(_CD8_TCELL[:12], _B_CELL[:12]):
        interleaved.extend([t, b])
    all_rows.extend(_make_cluster_rows(3, interleaved, n_filler=70, fc_top=3.5))

    df = pd.DataFrame(all_rows)
    df = df[["gene", "cluster", "avg_log2FC", "pct.1", "pct.2", "p_val", "p_val_adj"]]

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"✅ Mock FindAllMarkers saved: {out.resolve()}  ({len(df)} rows)")

    return df


def get_top_markers_for_cluster(df: pd.DataFrame, cluster_id: int,
                                 n: int = 50) -> list:
    """Pull top-N marker gene names for one cluster, ranked by log2FC."""
    sub = df[df["cluster"] == cluster_id].sort_values(
        "avg_log2FC", ascending=False
    )
    return sub["gene"].head(n).tolist()


# Quick self-test
if __name__ == "__main__":
    df = build_mock_findallmarkers("/tmp/test_mock.csv")
    print(df.head(15))
    print(f"\nClusters: {sorted(df['cluster'].unique())}")
    for c in sorted(df["cluster"].unique()):
        top10 = get_top_markers_for_cluster(df, c, n=10)
        print(f"  cluster {c} top10: {top10}")
