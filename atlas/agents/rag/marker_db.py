"""
ATLAS RAG — Marker Database Agent
=================================
Queries the precomputed CellMarker 2.0 slim CSV for canonical markers
associated with a given (species, tissue) combination.

Not an LLM agent — just pandas. Fast (~10ms per query).

Adapted from CASSIA paper Methods section (Marker Database agent).
"""

from pathlib import Path
from typing import Optional, List, Dict
import pandas as pd

# Cache: load CSV once, reuse across queries
_CACHED_DF: Optional[pd.DataFrame] = None
_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "cellmarker2_slim.csv"


def _load() -> pd.DataFrame:
    """Lazy-load the slim CellMarker CSV into memory once."""
    global _CACHED_DF
    if _CACHED_DF is None:
        if not _DATA_PATH.exists():
            raise FileNotFoundError(
                f"CellMarker slim CSV not found at {_DATA_PATH}. "
                "Run the data-prep step in the README, or "
                "download from CellMarker 2.0 and rerun preprocessing."
            )
        _CACHED_DF = pd.read_csv(_DATA_PATH)
    return _CACHED_DF


def query_cellmarker_for_tissue(
    species: str,
    tissue: str,
    top_n_celltypes: int = 15,
    markers_per_celltype: int = 8,
    include_undefined_tissue: bool = True,
) -> Dict[str, List[str]]:
    """
    Get canonical markers for cell types likely to be in this tissue.

    Args:
        species: "Human" or "Mouse" (case-insensitive).
        tissue: Free text, e.g. "Brain", "Peripheral blood", "Bone marrow".
                Matched against CellMarker's tissue_type column (case-insensitive).
        top_n_celltypes: Return the N most-represented cell types in this tissue.
        markers_per_celltype: Return up to M markers per cell type, ranked by
                              number of supporting publications.
        include_undefined_tissue: Also include cell types from tissue_type="Undefined"
                                  (these are tissue-agnostic generic types like immune
                                  cells that CellMarker uses when papers don't specify).

    Returns:
        Dict mapping cell_name → list of marker gene symbols (HGNC).
        Empty dict if nothing matches.
    """
    df = _load()

    # Normalize inputs
    species_norm = species.strip().capitalize()
    tissue_norm = tissue.strip().lower()

    # Filter species
    sub = df[df["species"].str.lower() == species_norm.lower()]
    if len(sub) == 0:
        return {}

    # Match tissue: exact (case-insensitive) preferred, fall back to substring
    exact = sub[sub["tissue_type"].str.lower() == tissue_norm]
    if len(exact) > 0:
        tissue_match = exact
    else:
        tissue_match = sub[sub["tissue_type"].str.lower().str.contains(
            tissue_norm, na=False, regex=False
        )]

    if include_undefined_tissue:
        undef = sub[sub["tissue_type"] == "Undefined"]
        tissue_match = pd.concat([tissue_match, undef], ignore_index=True)

    if len(tissue_match) == 0:
        return {}

    # Pick top-N cell types by total entries
    top_celltypes = (
        tissue_match["cell_name"].value_counts().head(top_n_celltypes).index.tolist()
    )

    # For each cell type, get top markers by publication count
    result: Dict[str, List[str]] = {}
    for cell in top_celltypes:
        cell_rows = tissue_match[tissue_match["cell_name"] == cell]
        # Count how many distinct entries support each marker
        markers = (
            cell_rows["Symbol"]
            .value_counts()
            .head(markers_per_celltype)
            .index.tolist()
        )
        if markers:
            result[cell] = markers

    return result


def format_marker_db_for_prompt(query_result: Dict[str, List[str]]) -> str:
    """
    Convert the marker-db query dict into a formatted text block ready
    to embed in the Annotator's prompt.
    """
    if not query_result:
        return "(No matching cell types found in CellMarker 2.0 for this tissue.)"
    lines = ["Cell types and canonical markers from CellMarker 2.0:"]
    for cell, markers in query_result.items():
        lines.append(f"  • {cell}: {', '.join(markers)}")
    return "\n".join(lines)


# Quick self-test when run directly
if __name__ == "__main__":
    print("Test 1: Human PBMC / Peripheral blood")
    res = query_cellmarker_for_tissue("Human", "Peripheral blood",
                                       top_n_celltypes=10, markers_per_celltype=6)
    print(format_marker_db_for_prompt(res))
