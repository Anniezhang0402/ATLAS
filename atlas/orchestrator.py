"""
ATLAS Orchestrator
=================================================================
Connects all 7 agents into a complete annotation workflow
  Marker gene input
        │
        ├─ (Optional) ScRAG Agent:
        │      Retrieve knowledge graph and vector-based evidence,
        │      then inject the retrieved context into additional_info.
        │
        ▼
  Core Annotation Pipeline
  (Annotator ⇄ Validator → Formatter → Scoring → Reporter)
        │
        ├─ (Conditional)
        │      If the quality score is below the threshold,
        │      invoke the Annotation Boost Agent for refinement.
        │
        ▼
  Final structured annotation result and report.
"""

from typing import Optional, List, Dict, Any

from .agents.core_agents import run_core_annotation
from .agents.annotation_boost import run_annotation_boost

def annotate_cluster(
    marker_list: List[str],
    tissue: Optional[str],
    species: str,
    model: Optional[str] = None,
    provider: str = "openrouter",
    temperature: float = 0,
    additional_info: str = "",
    scrag_agent=None,
    boost_threshold: int = 75,
    enable_boost: bool = True,
) -> Dict[str, Any]:
    """
    Run the complete ATLAS pipeline for a single cell cluster.

    Args:
        marker_list:
            Ranked marker genes for the cluster.

        tissue:
            Tissue type.
            If None or "tissue blind", use the tissue-blind workflow.

        species:
            Species name.

        scrag_agent:
            Optional ScRAGAgent instance.
            If provided, retrieved evidence is injected into the 
            annotation context before annotation begins.

        boost_threshold:
           Trigger Annotation Boost when score is below this threshold.

        enable_boost:
            Whether Annotation Boost is enabled.

    Returns:
        Dictionary containing:
            result
            history
            report
            boost

    """

    # ---------------------------------------------------------
    # Step 1
    # Optional ScRAG evidence retrieval
    # ---------------------------------------------------------

    if scrag_agent is not None:

        query = scrag_agent.build_query(
            tissue or "unknown",
            marker_list[:50],
        )

        evidence = scrag_agent.retrieve_evidence(query)

        additional_info = (
            additional_info
            + "\n\n[ScRAG Retrieved Evidence]\n"
            + evidence
        ).strip()

    # ---------------------------------------------------------
    # Step 2
    # Run the core annotation pipeline
    # ---------------------------------------------------------

    result, history, report = run_core_annotation(
        marker_list=marker_list,
        tissue=tissue,
        species=species,
        model=model,
        provider=provider,
        temperature=temperature,
        additional_info=additional_info,
    )

    output: Dict[str, Any] = {
        "result": result,
        "history": history,
        "report": report,
        "boost": None,
    }

    # ---------------------------------------------------------
    # Step 3
    # Conditionally run Annotation Boost
    # ---------------------------------------------------------

    score = (result or {}).get("score")

    needs_boost = (
        enable_boost
        and result is not None
        and (
            score is None
            or score < boost_threshold
        )
    )

    if needs_boost:
         
        cluster_info = (
            f"Species: {species}; "
            f"Tissue: {tissue or 'unknown'}"
        )

        annotation_text = "\n\n".join(
            [m[1] for m in history]
        )

        boost_final, boost_msgs = run_annotation_boost(
            major_cluster_info=cluster_info,
            comma_separated_genes=", ".join(marker_list),
            annotation_history=annotation_text,
            model=model,
            provider=provider,
            temperature=temperature,
        )

        output["boost"] = {
            "final": boost_final,
            "messages": boost_msgs,
        }

    return output