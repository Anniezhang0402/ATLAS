"""
ATLAS HTML Report Generator
===========================
Renders a pipeline `result` dict into a self-contained HTML file.

No LLM calls. Pure Python string templating + escaping.
"""

import html
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union

from atlas.reports.templates import CSS, PAGE_TEMPLATE


# ----------------- Helpers -----------------

def _escape_paragraphs(text: str) -> str:
    """
    HTML-escape user text and convert blank-line-separated paragraphs to <p>...</p>.
    Single newlines become <br>. Safe against `<script>` injection.
    """
    if not text:
        return ""
    escaped = html.escape(text)
    paragraphs = [p.strip() for p in escaped.split("\n\n") if p.strip()]
    return "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)


def _bullet_list(items: List[str], empty_text: str) -> str:
    if not items:
        return f'<li class="empty-list">{html.escape(empty_text)}</li>'
    return "".join(f"<li>{html.escape(str(it))}</li>" for it in items)


def _meta_pill(label: str, value: str) -> str:
    return (
        f'<span class="meta-item"><strong>{html.escape(label)}:</strong> '
        f'{html.escape(value)}</span>'
    )


# ----------------- Section renderers -----------------

def _render_annotator_section(conversation: List[Tuple[str, str]]) -> str:
    """Pull the LAST Annotator message (final reasoning) and render it."""
    annotator_msgs = [msg for spk, msg in conversation if "Annotator" in spk]
    if not annotator_msgs:
        return ""
    final_text = annotator_msgs[-1]
    return f"""
    <div class="agent-section final-annotation">
        <h2>🔬 Final Annotation Analysis</h2>
        {_escape_paragraphs(final_text)}
    </div>
    """


def _render_validator_section(conversation: List[Tuple[str, str]],
                              passed: bool) -> str:
    validator_msgs = [msg for spk, msg in conversation if "Validator" in spk]
    if not validator_msgs:
        return ""
    final_text = validator_msgs[-1]
    if passed:
        badge = '<div class="validation-result">✅ VALIDATION PASSED</div>'
    else:
        badge = '<div class="validation-result failed">⚠️ VALIDATION FAILED</div>'
    return f"""
    <div class="agent-section validator">
        <h2>🛡️ Validation Check</h2>
        {badge}
        {_escape_paragraphs(final_text)}
    </div>
    """


def _render_summary_section(structured: Optional[Dict[str, Any]],
                            num_markers: int) -> str:
    if not structured:
        return """
        <div class="agent-section formatting">
            <h2>📋 Summary</h2>
            <p class="empty-list">No structured output available (Formatter failed).</p>
        </div>
        """

    main = structured.get("main_cell_type", "Not specified")
    subs = structured.get("sub_cell_types", []) or []
    mixed = structured.get("possible_mixed_cell_types", []) or []

    return f"""
    <div class="agent-section formatting">
        <h2>📋 Summary</h2>
        <div class="summary-content">

            <div class="summary-item">
                <span class="summary-label">Main Cell Type</span>
                <span class="summary-value">{html.escape(str(main))}</span>
            </div>

            <div class="summary-item">
                <span class="summary-label">Sub Cell Types</span>
                <ul class="summary-list">
                    {_bullet_list(subs, "No sub cell types identified")}
                </ul>
            </div>

            <div class="summary-item">
                <span class="summary-label">Possible Mixed Cell Types</span>
                <ul class="summary-list">
                    {_bullet_list(mixed, "No mixed cell types identified")}
                </ul>
            </div>

            <div class="summary-item">
                <span class="summary-label">Number of Markers</span>
                <span class="summary-value">{num_markers}</span>
            </div>

        </div>
    </div>
    """


def _render_scoring_section(score: Optional[int],
                            reasoning: Optional[str]) -> str:
    if score is None:
        return """
        <div class="agent-section scoring">
            <h2>🎯 Quality Assessment</h2>
            <p class="empty-list">Score not available.</p>
        </div>
        """
    low = score < 75
    badge_class = "score-badge low" if low else "score-badge"
    section_class = "agent-section scoring low" if low else "agent-section scoring"
    return f"""
    <div class="{section_class}">
        <h2>🎯 Quality Assessment</h2>
        <div class="{badge_class}">{score} / 100</div>
        {_escape_paragraphs(reasoning or '')}
    </div>
    """


# ----------------- Top-level API -----------------

def render_report(
    result: Dict[str, Any],
    species: str = "",
    tissue: str = "",
    marker_list: Optional[List[str]] = None,
    title: str = "ATLAS Analysis Report",
) -> str:
    """
    Render an ATLAS pipeline result into a complete HTML document string.

    Args:
        result: dict returned by annotate_cluster_full(). Must contain at minimum:
            - 'conversation': List[(speaker, msg)]
            - 'structured': dict or None
            - 'validation_passed': bool
            - 'score' (optional): int
            - 'score_reasoning' (optional): str
        species, tissue: For the header.
        marker_list: For counting + display.
        title: Browser tab title.

    Returns:
        Complete HTML as a string.
    """
    conversation: List[Tuple[str, str]] = result.get("conversation", [])
    structured = result.get("structured")
    val_passed = bool(result.get("validation_passed", False))
    score = result.get("score")
    score_reasoning = result.get("score_reasoning")
    n_markers = len(marker_list) if marker_list else (
        structured.get("num_markers", 0) if structured else 0
    )

    # Header meta pills
    meta_items = []
    if species:
        meta_items.append(_meta_pill("Species", species))
    if tissue:
        meta_items.append(_meta_pill("Tissue", tissue))
    meta_items.append(_meta_pill("Markers", str(n_markers)))
    if score is not None:
        meta_items.append(_meta_pill("Score", f"{score}/100"))

    # Subtitle = main cell type if available
    subtitle = "Comprehensive cell type analysis"
    if structured and structured.get("main_cell_type"):
        subtitle = f"Predicted: {structured['main_cell_type']}"

    # Render body
    body_parts = [
        _render_annotator_section(conversation),
        _render_validator_section(conversation, val_passed),
        _render_summary_section(structured, n_markers),
        _render_scoring_section(score, score_reasoning),
    ]

    return PAGE_TEMPLATE.format(
        title=html.escape(title),
        css=CSS,
        subtitle=html.escape(subtitle),
        meta_items="\n".join(meta_items),
        body="\n".join(body_parts),
    )


def save_report(
    result: Dict[str, Any],
    output_path: Union[str, Path],
    **kwargs,
) -> Path:
    """
    Render and write the report to disk. Returns the resolved Path.

    Extra kwargs forwarded to render_report().
    """
    html_str = render_report(result, **kwargs)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_str, encoding="utf-8")
    print(f"✅ Report saved: {path.resolve()}")
    return path
