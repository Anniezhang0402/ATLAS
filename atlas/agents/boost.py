"""
ATLAS Annotation Boost Agent
=============================
Iterative ReAct loop that refines a low-confidence annotation by:
  1) Generating cell-type hypotheses + asking which genes to check
  2) Looking those genes up in the FindAllMarkers DataFrame
  3) Feeding the stats back to the LLM
  4) Repeating until "FINAL ANNOTATION COMPLETED" or max iterations.
"""

import re
import pandas as pd
from typing import List, Dict, Tuple, Optional, Union
from atlas.llm_client import call_llm
from atlas.prompts.system_prompts import BOOST_HYPOTHESIS_PROMPT

_ALLOWED_STAT_COLUMNS = ["gene", "avg_log2FC", "pct.1", "pct.2", "p_val_adj"]
COMPLETION_MARKER = "FINAL ANNOTATION COMPLETED"

# ----------------- Query Agent: look up gene stats -----------------
def query_markers(genes: List[str], marker_df: pd.DataFrame) -> str:
    """
    Look up statistics for a list of genes in a FindAllMarkers DataFrame.
    
    Returns a formatted plain-text table suitable for inclusion in an LLM prompt. Genes not found in the Dataframe are listed in a footer note.

    Args:
        genes: Gene symbols to look up.
        marker_df: A FindAllMarkers-style DataFrame with at least a 'gene' column plus some of: avg_log2FC, pct.1, pct.2, p_val_adj.
    
    Returns:
        Formatted string.
    """
    if not genes:
        return "No genes requested."
      
    #Find which genes are in the dataframe.
    df_genes = set(marker_df["gene"].astype(str))
    found = [g for g in genes if g in df_genes]
    missing = [g for g in genes if g not in df_genes]

    if not found:
        return f"None of the requested genes were found in the differential expression results: {', '.join(genes)}"
    
    #subset and apply column whitelist
    sub = marker_df[marker_df["gene"].isin(found)].copy()
    keep_cols = [c for c in _ALLOWED_STAT_COLUMNS if c in sub.columns]
    sub = sub[keep_cols]

    #format numerics
    for col in sub.columns:
        if col == "gene":
            continue
        if "p_val" in col.lower():
            sub[col] = sub[col].apply(
                lambda x: f"{float(x):.2e}" if pd.notnull(x) else "NA"
            )
        else:
            sub[col] = sub[col].apply(
                lambda x: f"{float(x):.2f}" if pd.notnull(x) else "NA"
            )
          
    #preserve the order the llm asked in, when possible
    sub["__order__"] = sub["gene"].map({g: i for i, g in enumerate(found)})
    sub = sub.sort_values("__order__").drop(columns="__order__")

    out = sub.to_string(index=False)
    if missing:
        out += f"\n\nNote: The following genes were not found in the differential expression results: {', '.join(missing)}"
    return out

# ----------------- Tag extraction -----------------
_CHECK_GENES_PATTERN = re.compile(
    r"<check_genes>\s*(.*?)\s*</check_genes>", re.DOTALL
)

def extract_check_genes(text: str) -> List[str]:
    """Pull all unique gene symbols inside <check_genes>...</check_genes> tags."""
    matches = _CHECK_GENES_PATTERN.findall(text)
    all_genes = []
    for block in matches:
        # Allow comma- and whitespace-separated
        block = re.sub(r"[\[\]()]", "", block)
        parts = re.split(r"[,\s]+", block)
        all_genes.extend(p.strip() for p in parts if p.strip())
    # Preserve order while deduplicating
    seen = set()
    unique = []
    for g in all_genes:
        if g not in seen:
            seen.add(g)
            unique.append(g)
    return unique


# ----------------- Main ReAct loop -----------------
def run_annotation_boost(
    major_cluster_info: str,
    marker_df: pd.DataFrame,
    ranked_marker_list: List[str],
    annotation_history: str,
    num_iterations: int = 5,
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> Dict:
    """
    Run iterative hypothesis-driven refinement on a low-confidence cluster.

    Args:
        major_cluster_info: Free text describing dataset, e.g. "Human PBMC".
        marker_df: FindAllMarkers DataFrame for THIS cluster (already filtered).
        ranked_marker_list: Top marker gene names ranked by importance.
        annotation_history: The current annotation conversation (string).
        num_iterations: Max ReAct cycles before forcing a conclusion.
        model: Override default annotation-boost model.
        temperature: 0.0 for deterministic reasoning.
    
    Returns:
        {
          'final_text': str,                  # LLM's final reasoning + conclusion
          'completed': bool,                  # True if hit COMPLETION_MARKER
          'iterations_used': int,
          'genes_queried_per_iter': list[list[str]],
          'conversation': list[dict],         # full {role, content} history
        }
    """
    comma_separated_genes = ", ".join(ranked_marker_list)
    initial_prompt = BOOST_HYPOTHESIS_PROMPT.format(
        major_cluster_info=major_cluster_info,
        comma_separated_genes=comma_separated_genes,
        annotation_history=annotation_history,
    )

    messages = [{"role": "user", "content": initial_prompt}]
    genes_queried_per_iter = []
    completed = False

    for iteration in range(num_iterations):
        reply = call_llm(
            user_prompt="",
            messages=messages,
            agent="annotation_boost",
            model=model,
            temperature=temperature,
            max_tokens=4096,
        )

        messages.append({"role": "assistant", "content": reply})

        if COMPLETION_MARKER in reply:
            print(f"Boost completed at iteration {iteration + 1}")
            completed = True

            return {
                "final_text": reply,
                "completed": True,
                "iterations_used": iteration + 1,
                "genes_queried_per_iter": genes_queried_per_iter,
                "conversation": messages,
            }

        genes = extract_check_genes(reply)
        genes_queried_per_iter.append(genes)

        if genes:
            stat_table = query_markers(genes, marker_df)
            user_msg = (
                f"Here are the requested gene statistics:\n\n{stat_table}\n\n"
                "Continue your analysis. If you have enough information, finalize "
                f"with '{COMPLETION_MARKER}' followed by your conclusion."
            )
        else:
            user_msg = (
                "You did not request any genes via <check_genes> tags. "
                "Please either request specific genes for follow-up, or finalize "
                f"with '{COMPLETION_MARKER}' followed by your conclusion."
            )

        messages.append({"role": "user", "content": user_msg})
        print(f"   iter {iteration + 1}: requested {len(genes)} gene(s)")

    print(f"⚠️ Max iterations ({num_iterations}) reached, forcing conclusion")
    
    messages.append({
        "role": "user",
        "content": (
            "You have reached the maximum number of iterations. "
            "Please provide your final analysis and best-confidence conclusion now. "
            f"Begin with '{COMPLETION_MARKER}' on its own line."
        ),
    })

    final_reply = call_llm(
        user_prompt="",
        messages=messages,
        agent="annotation_boost",
        model=model,
        temperature=temperature,
        max_tokens=4096,
    )
    messages.append({"role": "assistant", "content": final_reply})

    return {
        "final_text": final_reply,
        "completed": COMPLETION_MARKER in final_reply,
        "iterations_used": num_iterations,
        "genes_queried_per_iter": genes_queried_per_iter,
        "conversation": messages,
    }

