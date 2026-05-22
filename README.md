<div align="center">

# ATLAS

**A**gentic **T**ools for **L**ayered **A**nnotation of **S**ingle-cells

*A faithful reimplementation of the CASSIA multi-agent LLM framework
for single-cell RNA-seq cell type annotation.*

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/paper-Nat%20Commun%202026-red)](https://doi.org/10.1038/s41467-025-67084-x)
[![Original](https://img.shields.io/badge/based%20on-CASSIA-orange)](https://github.com/ElliotXie/CASSIA)

[🇨🇳 中文文档](README_CN.md) ·
[📐 Architecture](docs/ARCHITECTURE.md) ·

</div>

---

## What is this?

ATLAS is a multi-agent LLM system that annotates single-cell
RNA-seq clusters with quality-scored, interpretable cell type predictions.

The goal is *faithful reproduction*: every architectural choice traces back
to either the published paper or the public CASSIA source code, with
explicit attribution. ATLAS uses **only OpenRouter** as its LLM provider
(versus CASSIA's multi-provider support) to keep the implementation small
and readable.

This project was built as a hands-on exercise in:
- Multi-agent LLM orchestration
- Faithful scientific software reproduction
- Working with biological knowledge bases (CellMarker 2.0, Cell Ontology)

## ✨ Highlights

- **Complete reproduction**: all 5 core agents + 2 optional agents from the paper
- **Validated on real data**: reproduces CASSIA's published case of detecting a
  gold-standard error (monocyte → enteric glial cells; *paper Fig. 6b*)
- **Self-contained**: includes preprocessed CellMarker 2.0 and Cell Ontology
- **One key, any model**: OpenRouter gives access to GPT-5, Claude Sonnet 4.5,
  Gemini, Llama, DeepSeek with the same code
- **Cost-aware**: ~$0.04 per cluster for the 4-agent default pipeline
- **HTML reports**: every annotation produces a publication-grade visual report

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a deep dive into each agent.

## 🚀 Quick Start (90 seconds)

### 1. Install

```bash
git clone https://github.com/YOUR_USERNAME/ATLAS.git
cd ATLAS
pip install -r requirements.txt
```

### 2. Set your OpenRouter API key

Get one at <https://openrouter.ai> (top up $5 — covers ~100 annotations):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

### 3. Annotate a cluster

```python
import sys
sys.path.insert(0, '.')

from atlas.pipeline import annotate_cluster_full

result = annotate_cluster_full(
    species="Human",
    tissue="PBMC",
    marker_list=["CD8A", "CD8B", "CD3D", "GZMK", "NKG7",
                 "CCL5", "IL7R", "PRF1", "TRAC", "GNLY"],
)

print(result["structured"])
# {'main_cell_type': 'CD8+ T cells',
#  'sub_cell_types': ['CD8+ Effector Memory T cells (TEM)', ...],
#  ...}

print(f"Quality score: {result['score']}/100")
```

### 4. Generate an HTML report

```python
from atlas.reports import save_report

save_report(
    result,
    output_path="cd8_t_cell_report.html",
    species="Human",
    tissue="PBMC",
    marker_list=marker_list,
)
# Open the HTML file in any browser.
```

## 📊 Validated Performance

These are real results from this repository's test suite, using the
CASSIA paper's example data:

| Test case | Outcome | Score | Notes |
|---|---|---|---|
| Clean CD8+ T cell (clear markers) | ✅ Correct | 92/100 | Baseline 4-agent pipeline |
| CD8+ T cell + RAG augmentation | ✅ Finer subtypes | 95/100 | Hierarchical Feature agent adds T-cell axes |
| Plasma cell (housekeeping-dominated markers) | ✅ Correct | 78/100 | Annotator sees past noise |
| **Monocyte (paper Fig 6b error case)** | ✅ **Identified gold-standard error** | 68/100 | Boost agent confirms enteric glial cells |
| Mixed T + B cell | ✅ Mixed population flagged | — | — |

All results reproducible — see [`docs/REPRODUCTION.md`](docs/REPRODUCTION.md).

## 💰 Cost Reference

Measured on real runs as of May 2026 (OpenRouter pricing):

| Pipeline | LLM calls | Typical cost | Use when |
|---|---|---|---|
| 3-agent (no Scoring) | 3 | ~$0.04 | Fast prototyping |
| 4-agent core (default) | 4 | ~$0.04 | Standard annotation |
| 4-agent + Boost | +5–9 | +$0.10 | Score < 75 clusters |
| 4-agent + RAG | +1 | +$0.05 | Complex / under-studied tissue |
| Full (4-agent + Boost + RAG) | up to 14 | ~$0.20 | Maximum confidence |

**Optimization tip**: Scoring uses DeepSeek v3 by default (~$0.001/call), and
Formatter uses Gemini Flash. Only Annotator/Validator/Boost use a strong
model like Claude Sonnet 4.5. Override any model per-agent via the
`*_model=` kwargs.

## 🧬 The 7 Agents

| # | Agent | LLM? | What it does |
|---|---|---|---|
| 1 | **Annotator** | ✅ | Chain-of-thought reasoning over the marker list to propose cell type + 3 subtypes |
| 2 | **Validator** | ✅ | Checks marker-celltype consistency, requests revision if needed (≤3 cycles) |
| 3 | **Formatter** | ✅ | Converts free-text annotation into strict JSON |
| 4 | **Scoring** | ✅ | Assigns 0-100 quality score based on marker balance and scientific accuracy |
| 5 | **Reporter** | ❌ | Renders the full conversation into a styled HTML report |
| 6 | **Annotation Boost** *(optional)* | ✅ | ReAct loop: hypothesize → query gene statistics from FindAllMarkers → refine. Rescues low-confidence cases |
| 7 | **RAG** *(optional)* | ✅ | 3 sub-agents: queries CellMarker 2.0 (Marker DB) + Cell Ontology + LLM-driven feature axis analysis |




## ⚖️ License

MIT — same as CASSIA. See [LICENSE](LICENSE).
