# ATLAS Architecture

This document is a deep dive into ATLAS's design decisions: what each
agent does, how it differs from CASSIA, and why.

## Design Principles

1. **One provider, one auth flow**: OpenRouter only. Loses CASSIA's
   provider portability, but eliminates 600+ lines of branching.
2. **Explicit over implicit**: agents pass full conversation history as
   an argument, not via a shared `additional_params['messages']` convention.
3. **Per-agent model defaults**: cheap models for routine work
   (Formatter, Scoring), strong models for reasoning (Annotator, Boost).
4. **Reproducibility first**: prompts live in `atlas/prompts/`
   (single source of truth) and are versioned with the code.

## Core 5-Agent Pipeline

### 1. Annotator (LLM)

- **Source**: `atlas/agents/base.py` (`Agent` class) + `atlas/prompts/system_prompts.py`
- **System prompt**: Adapted verbatim from CASSIA's `final_annotation_system_v1`,
  with minor formatting fixes.
- **Loop logic**: Calls itself up to 5 times until output contains the
  string `"FINAL ANNOTATION COMPLETED"`. Mirrors CASSIA's design.
- **Model default**: `anthropic/claude-sonnet-4.5` — strong reasoning matters.
- **Per-counterpart memory**: same agent maintains separate conversation
  histories with `"user"` and `"validator"` counterparts (mirrors CASSIA).

### 2. Validator (LLM)

- **Same `Agent` class**, different system prompt
  (`VALIDATOR_SYSTEM` in `prompts/system_prompts.py`).
- **Output format**: "VALIDATION PASSED" or "VALIDATION FAILED" string —
  intentionally not JSON, to be robust to LLM formatting drift.
- **Loop**: If validation fails, the Annotator gets a *structured feedback*
  message (previous output + validator feedback + original prompt) and
  retries up to 3 times.

### 3. Formatter (LLM)

- **Job**: convert free-text annotation to strict JSON
  (`main_cell_type`, `sub_cell_types`, `possible_mixed_cell_types`).
- **JSON extraction**: regex pulls content from ` ```json ... ``` ` fences,
  parses with `json.loads(strict=False)` to tolerate embedded newlines.
- **Model default**: `google/gemini-2.5-flash` — formatting is mechanical,
  cheap model suffices.

### 4. Scoring (LLM, stateless function)

- **Source**: `atlas/agents/scoring.py`
- **Not** an `Agent` instance — just one stateless call.
- **System prompt**: adapted from CASSIA's `prompt_creator_score`.
- **Output format**: `<reasoning>...</reasoning><score>NN</score>` XML tags.
- **7-way regex fallback**: tolerates `Score: NN`, `NN/100`, `NN%`, etc.
- **Model default**: `deepseek/deepseek-chat-v3-0324` — 30× cheaper than
  Claude, sufficient for evaluation.

### 5. Reporter (no LLM)

- **Source**: `atlas/reports/html_report.py` + `templates.py`
- **Pure Python string templating** — no LLM calls.
- **Input**: the `result` dict from `annotate_cluster_full()`.
- **Output**: a self-contained HTML file with CSS embedded.
- **Difference from CASSIA**: CASSIA passes conversation as a
  `|||SECTION|||`-delimited string, which is brittle. ATLAS reads from
  the structured dict directly. Also adds HTML escaping (CASSIA doesn't,
  which is a minor XSS risk for malicious markers).

## Optional Agents

### 6. Annotation Boost (LLM, ReAct loop)

- **Source**: `atlas/agents/boost.py`
- **When triggered**: typically when Scoring returns < 75.
- **Algorithm** (mirrors CASSIA's `iterative_marker_analysis`):
  1. LLM generates ≤3 cell-type hypotheses, marks genes to check via
     `<check_genes>GENE1,GENE2,...</check_genes>` tags.
  2. Python extracts those genes, queries the FindAllMarkers DataFrame
     (full statistics: `avg_log2FC`, `pct.1`, `pct.2`, `p_val_adj`).
  3. Results fed back to LLM as the next user message.
  4. Loop up to 5 times or until LLM emits `"FINAL ANNOTATION COMPLETED"`.
- **Why it works**: gives the LLM a *tool* (gene-stat lookup) to test
  hypotheses, rather than relying on its parametric knowledge alone.
- **Verified case**: paper Fig. 6b's monocyte → enteric glial cell
  rescue is reproduced in ATLAS — see [REPRODUCTION.md](REPRODUCTION.md).

### 7. RAG (3 sub-agents)

- **Source**: `atlas/agents/rag/`
- **Note**: CASSIA's *public* RAG implementation
  (`agents/reference_agent/`) was substantially rewritten between paper
  publication and the v1.2 release — it now relies on private Markdown
  knowledge bases. ATLAS therefore reimplements RAG from the **paper's
  Methods description** (independent implementation), giving:
  - **Marker Database Agent** (no LLM): pandas query on the preprocessed
    CellMarker 2.0 CSV. Returns top cell types + canonical markers for
    `(species, tissue)`.
  - **Ontology Database Agent** (no LLM): `obonet` + `networkx` traversal
    of Cell Ontology. Returns ancestor chains for the cell types.
  - **Hierarchical Feature Agent** (LLM): given the marker + ontology
    context, identifies 2–4 biological *discriminative axes* (e.g.
    "adaptive vs innate immunity", "naive vs memory") and the markers
    that resolve each axis.
- **Output**: a single text block prepended to Annotator's
  `additional_info`.
- **Cross-Species agent**: skipped (covered only in paper, no production
  use in CASSIA). Easy to add later.

## Differences from CASSIA

| Aspect | CASSIA | ATLAS |
|---|---|---|
| LLM providers | OpenAI, Anthropic, OpenRouter, custom | OpenRouter only |
| Lines of code | ~25,000 (Python + R) | ~2,500 (Python only) |
| Conversation passing | implicit (`additional_params['messages']`) | explicit (`messages=` arg) |
| Subclustering agent | included | not implemented |
| Uncertainty quantification (multi-run CS score) | included | not implemented |
| Reporter delimiter | `\|\|\|SECTION\|\|\|` string | structured dict |
| HTML escaping | no | yes |
| Mock data generator | no | `atlas/utils/mock_data.py` (now deprecated, see `load_cassia_data.py`) |
| Per-agent model defaults | JSON config file | Python dict (`DEFAULT_MODELS`) |
| RAG knowledge base | private Markdown collection (recent rewrite) | CellMarker 2.0 + Cell Ontology (paper Methods) |

These are intentional simplifications, not feature omissions:
CASSIA's "completeness" reflects two years of feature accumulation that
isn't necessary to reproduce the paper's central claims.

## Data Resources

- `data/cellmarker2_slim.csv` (4.3 MB)
  - Preprocessed from CellMarker 2.0's `Cell_marker_All.xlsx` (9.5 MB).
  - Kept columns: `species`, `tissue_type`, `cell_name`, `Symbol`,
    `cellontology_id`, `marker_source`.
  - Filtered to Normal entries (no cancer), Symbol non-null, dedup.
  - Result: 64,169 unique (species, tissue, cell_type, marker) quadruples.
- `data/cl.obo` (3.2 MB)
  - Cell Ontology *simple* OBO format from OBO Foundry.
  - 3,324 cell type nodes, 5,109 relationships.
  - Parsed via `obonet` (much lighter than `owlready2`).

Both are version-controlled in the repo — no runtime downloads needed.
