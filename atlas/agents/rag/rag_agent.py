"""
ATLAS RAG — Top-level Agent
===========================
Orchestrates 3 sub-agents to assemble background knowledge for the
Annotator:

  1. Marker Database Agent (pandas query, no LLM)
     → Canonical markers for cell types likely in this tissue
  2. Ontology Database Agent (graph query, no LLM)
     → Ancestor chains showing how cell types are related
  3. Hierarchical Feature Agent (LLM)
     → Identifies discriminative biological axes
       (e.g. "excitatory vs inhibitory", "naive vs memory")
       and the markers that resolve each axis

Output: A single context string to prepend to Annotator's prompt.

Adapted from CASSIA paper Methods section (RAG pipeline).
"""

from typing import List, Optional
from atlas.llm_client import call_llm
from atlas.agents.rag.marker_db import (
    query_cellmarker_for_tissue,
    format_marker_db_for_prompt,
)
from atlas.agents.rag.ontology import build_tissue_hierarchy


# ----------------- Hierarchical Feature Agent (LLM) -----------------

HIERARCHICAL_FEATURE_SYSTEM = """\
You are an expert in cell biology and developmental immunology. Your task
is to analyze a set of related cell types and identify the BIOLOGICAL AXES
along which they differ — like principal components in a low-dimensional
embedding, but conceptual rather than numerical.

For each major axis you identify, list 3-6 marker genes whose expression
PATTERN (high/low/absent) discriminates cell types along that axis.

Output STRICT format, no extra commentary:

Axis 1: [Short name, e.g. "excitatory vs inhibitory neurotransmission"]
  Markers: GENE1, GENE2, GENE3
  Logic: One sentence on what pattern means what.

Axis 2: ...

Provide 2-4 axes. Stop. Do not include preamble, conclusions, or
explanations outside the listed format.
"""


def _build_feature_prompt(tissue: str, hierarchy_text: str,
                          marker_db_text: str) -> str:
    return f"""\
TISSUE: {tissue}

CELL TYPE HIERARCHY (from Cell Ontology):
{hierarchy_text}

CANONICAL MARKERS (from CellMarker 2.0):
{marker_db_text}

Based on this, identify 2-4 BIOLOGICAL AXES that discriminate these cell
types, and the markers that resolve each axis. Follow the strict output
format.
"""


def analyze_hierarchical_features(
    tissue: str,
    hierarchy_text: str,
    marker_db_text: str,
    model: Optional[str] = None,
) -> str:
    """Run the Hierarchical Feature LLM agent. Returns its raw output text."""
    user_msg = _build_feature_prompt(tissue, hierarchy_text, marker_db_text)
    reply = call_llm(
        user_prompt=user_msg,
        system_prompt=HIERARCHICAL_FEATURE_SYSTEM,
        agent="rag",
        model=model,
        temperature=0.0,
        max_tokens=2048,
    )
    return reply.strip()


# ----------------- Top-level orchestrator -----------------

def build_rag_context(
    species: str,
    tissue: str,
    top_n_celltypes: int = 12,
    markers_per_celltype: int = 6,
    feature_model: Optional[str] = None,
    skip_feature_analysis: bool = False,
) -> str:
    """
    Build the complete RAG context block to prepend to Annotator's prompt.

    Args:
        species: "Human" or "Mouse".
        tissue: Free text tissue name.
        top_n_celltypes: How many cell types to pull from CellMarker.
        markers_per_celltype: Markers per cell type.
        feature_model: LLM model for the hierarchical feature step.
        skip_feature_analysis: If True, skip the LLM call and only return
                               the pandas+ontology output (saves cost/time).

    Returns:
        Multi-section text block ready to embed in a prompt.
    """
    # --- Step 1: Marker DB ---
    marker_db = query_cellmarker_for_tissue(
        species=species,
        tissue=tissue,
        top_n_celltypes=top_n_celltypes,
        markers_per_celltype=markers_per_celltype,
    )
    marker_db_text = format_marker_db_for_prompt(marker_db)

    # --- Step 2: Ontology hierarchy ---
    if marker_db:
        hierarchy_text = build_tissue_hierarchy(list(marker_db.keys()))
    else:
        hierarchy_text = "(No cell types to build hierarchy from.)"

    # --- Step 3: Hierarchical Feature LLM agent (optional) ---
    if skip_feature_analysis or not marker_db:
        feature_text = "(Hierarchical feature analysis skipped.)"
    else:
        feature_text = analyze_hierarchical_features(
            tissue=tissue,
            hierarchy_text=hierarchy_text,
            marker_db_text=marker_db_text,
            model=feature_model,
        )

    # --- Assemble ---
    return f"""\
=== RAG BACKGROUND KNOWLEDGE (for reference) ===

[Section 1] Canonical markers for cell types known in this tissue:
{marker_db_text}

[Section 2] How these cell types are related (Cell Ontology hierarchy):
{hierarchy_text}

[Section 3] Discriminative biological axes among these cell types:
{feature_text}

=== END RAG BACKGROUND ===
"""
