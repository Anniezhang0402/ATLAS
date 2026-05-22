"""
ATLAS Webapp — Streamlit Main Entry
====================================
A demo/showcase web interface for the 7-agent ATLAS pipeline.

Run locally:
    cd ATLAS
    source .venv/bin/activate
    streamlit run webapp/app.py

The app expects users to supply their own OpenRouter API key
(stored in session state only, never persisted server-side).
"""

import sys
from pathlib import Path

# Make ATLAS importable when run with `streamlit run webapp/app.py`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

# ---------- Page config (MUST be the first Streamlit call) ----------
st.set_page_config(
    page_title="ATLAS — Single-cell annotation",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Now the heavier ATLAS imports
from atlas.pipeline import annotate_cluster_full  # noqa: E402
from atlas.reports.html_report import render_report  # noqa: E402

from webapp.style import CUSTOM_CSS
from webapp.components import (
    render_hero,
    render_sidebar,
    render_result_summary,
    render_reasoning,
)
from webapp.demo_cases import DEMO_CASES


# ---------- Apply custom CSS ----------
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------- Hero + sidebar ----------
render_hero()
settings = render_sidebar()


# ---------- Helper: run pipeline with progress feedback ----------
def run_pipeline(species, tissue, markers, additional_info, settings):
    """Run ATLAS with live progress updates. Returns the result dict."""
    if not settings["api_key"]:
        st.error("Please enter your OpenRouter API key in the sidebar first.")
        return None

    progress = st.empty()
    progress.info("🤖 Annotator is reasoning over the marker list...")

    annotator_model = settings["annotator_model"]
    rag_context = None

    # If RAG enabled, build context first
    if settings["use_rag"]:
        progress.info("🔍 RAG: Querying CellMarker 2.0 and Cell Ontology...")
        try:
            from atlas.agents.rag.rag_agent import build_rag_context
            rag_context = build_rag_context(
                species=species,
                tissue=tissue,
                top_n_celltypes=10,
                markers_per_celltype=6,
            )
            additional_info = f"{rag_context}\n\n{additional_info}".strip()
        except Exception as e:
            st.warning(f"RAG step failed, continuing without it: {e}")

    progress.info("🤖 Running 4-agent pipeline (Annotator → Validator → Formatter → Scoring)...")

    try:
        result = annotate_cluster_full(
            species=species,
            tissue=tissue,
            marker_list=markers,
            additional_info=additional_info,
            annotator_model=annotator_model,
        )
    except Exception as e:
        progress.empty()
        st.error(f"Pipeline failed: {e}")
        return None

    # Optionally run Boost on low score
    if settings["use_boost_on_low"] and result.get("score_flagged_low"):
        progress.info(
            f"⚠️ Score {result['score']}/100 < 75 — running Annotation Boost..."
        )
        # Note: Boost needs full FindAllMarkers DataFrame. For demo cluster
        # without that, we skip with a friendly note.
        st.warning(
            "Boost requires full FindAllMarkers statistics (avg_log2FC, pct.1, "
            "pct.2, p_val_adj). The web demo uses only a marker list, so Boost "
            "isn't available here. Run Boost from a Python script with your "
            "Seurat / Scanpy output."
        )

    progress.empty()
    if rag_context:
        result["rag_context"] = rag_context
    return result


# ---------- Tab Navigation ----------
tab_try, tab_demos, tab_about = st.tabs([
    "🚀 Try It",
    "🎬 Demo Cases",
    "📐 About",
])


# ====================================================================
# TAB 1: Try It Yourself
# ====================================================================
with tab_try:
    st.subheader("Annotate your own cluster")
    st.markdown(
        "Provide a ranked list of marker genes for a single cluster, "
        "and ATLAS will run all 4 core agents to identify the cell type."
    )

    col_inp1, col_inp2 = st.columns(2)
    with col_inp1:
        species = st.selectbox("Species", ["Human", "Mouse"], key="try_species")
    with col_inp2:
        tissue = st.text_input("Tissue", value="PBMC",
                               key="try_tissue",
                               help="Free text; e.g. 'PBMC', 'Brain', 'Bone marrow'")

    markers_text = st.text_area(
        "Marker genes (comma-separated, ranked by importance)",
        value="CD8A, CD8B, CD3D, CD3E, GZMK, NKG7, CCL5, IL7R, PRF1, TRAC",
        key="try_markers",
        height=100,
        help="Paste the top 10-50 marker gene symbols from FindAllMarkers, "
             "ordered by descending log2FC.",
    )

    additional_info = st.text_input(
        "Additional context (optional)",
        value="",
        key="try_info",
        help="Anything else relevant: disease state, treatment, age, etc.",
    )

    if st.button("▶ Run Annotation", type="primary", key="try_run"):
        markers = [m.strip().upper() for m in markers_text.split(",") if m.strip()]
        if len(markers) < 5:
            st.error("Please provide at least 5 marker genes.")
        else:
            result = run_pipeline(species, tissue, markers, additional_info, settings)
            if result:
                st.session_state["last_result"] = result
                st.session_state["last_markers"] = markers
                st.session_state["last_species"] = species
                st.session_state["last_tissue"] = tissue

    # Show results if available
    if "last_result" in st.session_state:
        st.markdown("---")
        st.markdown("### 🎯 Result")
        render_result_summary(st.session_state["last_result"])

        st.markdown("### 🧠 Reasoning")
        render_reasoning(st.session_state["last_result"])

        # Generate downloadable HTML report
        st.markdown("### 📥 Download")
        html_str = render_report(
            st.session_state["last_result"],
            species=st.session_state.get("last_species", ""),
            tissue=st.session_state.get("last_tissue", ""),
            marker_list=st.session_state.get("last_markers", []),
            title="ATLAS Annotation Report",
        )
        st.download_button(
            label="📄 Download full HTML report",
            data=html_str,
            file_name="atlas_report.html",
            mime="text/html",
        )


# ====================================================================
# TAB 2: Demo Cases
# ====================================================================
with tab_demos:
    st.subheader("Click-to-run demo cases")
    st.markdown(
        "Three pre-curated cell clusters showcasing different ATLAS strengths. "
        "Each runs the full 4-agent pipeline (~30 seconds, ~$0.04 with Claude Sonnet)."
    )

    for case_key, case in DEMO_CASES.items():
        with st.expander(f"**{case['label']}** — {case['description']}",
                         expanded=False):

            st.markdown(f"**Species:** {case['species']}  ·  "
                        f"**Tissue:** {case['tissue']}")
            st.markdown(f"**Top markers:** `{', '.join(case['markers'][:10])}...`")
            st.markdown(f"**Expected outcome:** {case['expected_celltype']}")

            if st.button(f"▶ Run this case", key=f"demo_{case_key}"):
                result = run_pipeline(
                    species=case["species"],
                    tissue=case["tissue"],
                    markers=case["markers"],
                    additional_info=case["additional_info"],
                    settings=settings,
                )
                if result:
                    st.session_state[f"demo_result_{case_key}"] = result

            # Show result if this case has been run
            if f"demo_result_{case_key}" in st.session_state:
                st.markdown("---")
                render_result_summary(st.session_state[f"demo_result_{case_key}"])
                with st.expander("🧠 View full reasoning", expanded=False):
                    render_reasoning(st.session_state[f"demo_result_{case_key}"])


# ====================================================================
# TAB 3: About
# ====================================================================
with tab_about:
    st.subheader("About ATLAS")

    st.markdown("""
ATLAS is an **independent Python reimplementation** of the CASSIA framework
(Xie et al., *Nature Communications* 2026), built as a learning exercise in
multi-agent LLM orchestration and faithful scientific software reproduction.

### 🤖 The 7 Agents
""")

    agent_info = [
        ("1. **Annotator**", "LLM", "Chain-of-thought reasoning on the marker list"),
        ("2. **Validator**", "LLM", "Checks marker-celltype consistency, up to 3 cycles"),
        ("3. **Formatter**", "LLM", "Converts free-text annotation into structured JSON"),
        ("4. **Scoring**", "LLM", "Assigns 0-100 quality score"),
        ("5. **Reporter**", "no LLM", "Generates HTML visual report"),
        ("6. **Annotation Boost**", "LLM (optional)", "ReAct loop with FindAllMarkers queries; rescues low-confidence cases"),
        ("7. **RAG**", "LLM + Data (optional)", "CellMarker 2.0 + Cell Ontology + Hierarchical Feature analysis"),
    ]
    for name, kind, desc in agent_info:
        st.markdown(f"- {name} *({kind})* — {desc}")

    st.markdown("""
### 🧬 Data resources

- **CellMarker 2.0** — 64,169 (species, tissue, cell type, marker) entries
  preprocessed from the Harbin Medical University database
- **Cell Ontology** — 3,324 cell type nodes, 5,109 hierarchical relationships
  from OBO Foundry

### 💡 Why a reproduction?

CASSIA is a state-of-the-art tool. Reimplementing it from scratch (paper +
public code) is one of the best ways to learn multi-agent LLM systems.
Every architectural choice in ATLAS is traceable to either the paper or
CASSIA's source code (MIT licensed).

### 📖 Cite

If ATLAS is useful, please cite the **original CASSIA paper**:
> Xie E. et al. CASSIA: a multi-agent large language model for automated
> and interpretable cell annotation. *Nat Commun* 17, 389 (2026).
> https://doi.org/10.1038/s41467-025-67084-x
""")

