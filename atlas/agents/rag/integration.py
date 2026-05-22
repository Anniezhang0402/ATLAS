"""
ATLAS RAG — Integration helper
==============================
Convenience function to plug RAG context into the existing pipeline.
"""

from typing import Optional, List, Dict, Any
from atlas.pipeline import annotate_cluster_full
from atlas.agents.rag.rag_agent import build_rag_context


def annotate_cluster_with_rag(
    species: str,
    tissue: str,
    marker_list: List[str],
    additional_info: str = "",
    rag_skip_feature_analysis: bool = False,
    **pipeline_kwargs,
) -> Dict[str, Any]:
    """
    Run the full 4-agent pipeline (Annotator/Validator/Formatter/Scoring)
    with RAG context prepended to the user-provided additional_info.

    All pipeline_kwargs (annotator_model, etc.) forwarded to annotate_cluster_full.
    """
    rag_text = build_rag_context(
        species=species,
        tissue=tissue,
        skip_feature_analysis=rag_skip_feature_analysis,
    )
    augmented_info = f"{rag_text}\n\n{additional_info}".strip()
    result = annotate_cluster_full(
        species=species,
        tissue=tissue,
        marker_list=marker_list,
        additional_info=augmented_info,
        **pipeline_kwargs,
    )
    result["rag_context"] = rag_text  # for inspection
    return result
