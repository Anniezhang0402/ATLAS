"""
ATLAS Webapp — Reusable UI components.
"""

import streamlit as st
from typing import Dict, Any, Optional


def render_hero():
    """Big gradient title at the top of every page."""
    st.markdown(
        """
        <div class="atlas-hero">
            <h1 class="atlas-hero-title">ATLAS</h1>
            <div class="atlas-hero-subtitle">
                Agentic Tools for Layered Annotation of Single-cells
            </div>
            <div class="atlas-hero-tagline">
                A 7-agent LLM pipeline · Faithful reproduction of CASSIA (Nat Commun 2026)
            </div>
            <div class="atlas-badges">
                <span class="atlas-badge">🤖 7 agents</span>
                <span class="atlas-badge">🧬 96k markers</span>
                <span class="atlas-badge">📐 Cell Ontology</span>
                <span class="atlas-badge">💰 ~$0.04 / cluster</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")


def render_sidebar() -> Dict[str, Any]:
    """
    Left sidebar: API key + pipeline options.
    Returns a dict of user settings.
    """
    with st.sidebar:
        st.markdown("## 🔑 OpenRouter API Key")

        # Persist key across reruns
        key = st.text_input(
            "Your OpenRouter API key",
            type="password",
            value=st.session_state.get("api_key", ""),
            help="Get a free key at openrouter.ai (top up $5 ≈ 100 annotations)",
            placeholder="sk-or-v1-...",
        )
        if key:
            st.session_state["api_key"] = key
            import os
            os.environ["OPENROUTER_API_KEY"] = key
            st.success("Key set ✓")
        else:
            st.info("→ [Get key at openrouter.ai](https://openrouter.ai/settings/keys)")

        st.markdown("---")
        st.markdown("## ⚙️ Pipeline Options")

        use_rag = st.checkbox(
            "🔍 Enable RAG augmentation",
            value=False,
            help="Adds Marker DB + Cell Ontology context to the Annotator. "
                 "Improves accuracy on complex/unfamiliar tissues. +1 LLM call.",
        )

        use_boost_on_low = st.checkbox(
            "🚀 Auto-run Boost when score < 75",
            value=False,
            help="If quality score is low, runs the Annotation Boost ReAct loop "
                 "to refine the annotation. +4-9 LLM calls.",
        )

        st.markdown("---")
        st.markdown("## 🎛️ Models")

        annotator_choice = st.selectbox(
            "Annotator model",
            [
                "anthropic/claude-sonnet-4.5",
                "openai/gpt-5.1",
                "google/gemini-2.5-flash",
                "deepseek/deepseek-chat-v3-0324",
            ],
            index=0,
            help="Strong models (Claude/GPT) give better reasoning. "
                 "Fast models (Gemini/DeepSeek) are cheaper.",
        )

        st.markdown("---")

        # Usage / cost tracker
        from atlas.llm_client import get_usage_summary
        usage = get_usage_summary()
        if usage["n_calls"] > 0:
            st.markdown("## 💰 Session Usage")
            st.metric("LLM calls", usage["n_calls"])
            st.metric("Total cost",
                      f"${usage['cost_usd']:.4f}" if usage['cost_usd'] else "—")

        st.markdown("---")
        st.markdown(
            "<small>"
            "📖 [Paper](https://doi.org/10.1038/s41467-025-67084-x) · "
            "💻 [GitHub](https://github.com/)"
            "</small>",
            unsafe_allow_html=True,
        )

    return {
        "api_key": key,
        "use_rag": use_rag,
        "use_boost_on_low": use_boost_on_low,
        "annotator_model": annotator_choice,
    }


def render_score_badge(score: Optional[int]):
    """Big colored score pill: green ≥75, amber 50-74, red <50."""
    if score is None:
        st.markdown("Score: _not available_")
        return
    if score >= 75:
        css_class = "score-badge score-high"
        emoji = "🟢"
    elif score >= 50:
        css_class = "score-badge score-mid"
        emoji = "🟡"
    else:
        css_class = "score-badge score-low"
        emoji = "🔴"
    st.markdown(
        f'<div class="{css_class}">{emoji} {score} / 100</div>',
        unsafe_allow_html=True,
    )


def render_result_summary(result: Dict[str, Any]):
    """Pretty colored cards showing the main annotation summary."""
    structured = result.get("structured") or {}
    main = structured.get("main_cell_type", "—")
    subs = structured.get("sub_cell_types", []) or []
    mixed = structured.get("possible_mixed_cell_types", []) or []

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-card-title">Main Cell Type</div>
                <div class="result-card-value">{main}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if subs:
            st.markdown("**Sub-cell types:**")
            for s in subs:
                st.markdown(f"  • {s}")
        if mixed:
            st.markdown("**Possible mixed populations:**")
            for m in mixed:
                st.markdown(f"  • {m}")

    with col2:
        st.markdown("**Quality Score**")
        render_score_badge(result.get("score"))
        passed = result.get("validation_passed", False)
        if passed:
            st.success("✅ Validation passed")
        else:
            st.warning("⚠️ Validation failed")


def render_reasoning(result: Dict[str, Any]):
    """Collapsible Annotator/Validator reasoning blocks."""
    convo = result.get("conversation", [])
    if not convo:
        st.info("No conversation history available.")
        return

    # Group by speaker, keep order
    last_speaker = None
    for speaker, msg in convo:
        with st.expander(f"💬 {speaker}", expanded=False):
            st.markdown(msg)
