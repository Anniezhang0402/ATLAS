"""
ATLAS RAG — Ontology Database Agent
===================================
Queries Cell Ontology (CL) for cell-type hierarchies.

Uses `obonet` (not `owlready2`) — same expressive power for our needs
(is_a relationships), but 10x lighter and easier to install.

Adapted from CASSIA paper Methods section (Ontology Database agent).
"""

from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple
import obonet
import networkx as nx

# Cache: load OBO once
_CACHED_GRAPH: Optional[nx.MultiDiGraph] = None
_NAME_TO_ID_CACHE: Optional[Dict[str, str]] = None
_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "cl.obo"


def load_cell_ontology() -> nx.MultiDiGraph:
    """Load Cell Ontology graph once and reuse."""
    global _CACHED_GRAPH, _NAME_TO_ID_CACHE
    if _CACHED_GRAPH is None:
        if not _DATA_PATH.exists():
            raise FileNotFoundError(
                f"Cell Ontology OBO not found at {_DATA_PATH}. "
                "Download from https://purl.obolibrary.org/obo/cl/cl-simple.obo "
                "and place in ATLAS/data/."
            )
        _CACHED_GRAPH = obonet.read_obo(str(_DATA_PATH))
        # Build name → CL_id lookup table
        _NAME_TO_ID_CACHE = {}
        for cl_id, node in _CACHED_GRAPH.nodes(data=True):
            name = node.get("name", "")
            if name:
                _NAME_TO_ID_CACHE[name.lower()] = cl_id
            # Also index synonyms for fuzzy matching
            for syn in node.get("synonym", []):
                # OBO synonym format: '"actual name" EXACT []'
                syn_name = syn.split('"')[1] if '"' in syn else ""
                if syn_name:
                    _NAME_TO_ID_CACHE.setdefault(syn_name.lower(), cl_id)
    return _CACHED_GRAPH


def cell_name_to_id(name: str) -> Optional[str]:
    """Look up a CL_id from a free-text cell name (case-insensitive, synonyms aware)."""
    load_cell_ontology()
    return _NAME_TO_ID_CACHE.get(name.lower().strip())


def get_ancestor_chain(cell_name: str, max_depth: int = 8) -> List[Tuple[str, str]]:
    """
    Walk up the is_a hierarchy from a cell name, following primary parents only.

    Args:
        cell_name: e.g. "CD8-positive, alpha-beta T cell"
        max_depth: Stop after this many parent levels.

    Returns:
        List of (cl_id, cl_name) tuples, from specific → general.
        Empty list if cell_name not found in ontology.
    """
    g = load_cell_ontology()
    cl_id = cell_name_to_id(cell_name)
    if cl_id is None:
        return []

    chain: List[Tuple[str, str]] = []
    current = cl_id
    visited: Set[str] = set()

    for _ in range(max_depth):
        if current in visited:
            break
        visited.add(current)
        name = g.nodes[current].get("name", current)
        chain.append((current, name))
        # Follow only is_a edges (obonet stores them as 'is_a' edge attribute)
        is_a_parents = []
        for u, v, data in g.out_edges(current, data=True):
            # In obonet's graph, edge u→v means u is_a v (or other relationship)
            # We need to check the 'is_a' edge type
            if g.has_edge(u, v):
                edges = g.get_edge_data(u, v)
                for key, attrs in edges.items():
                    if key == "is_a":
                        is_a_parents.append(v)
                        break
        if not is_a_parents:
            break
        # Take the first is_a parent (primary lineage)
        current = is_a_parents[0]
    return chain


def get_cell_types_for_tissue(
    tissue_name: str,
    cellmarker_celltypes: List[str],
) -> Dict[str, str]:
    """
    Given a list of cell-type NAMES (from CellMarker query), look up their
    CL_ids so downstream code can navigate the ontology.

    This is the bridge between CellMarker (text names) and Cell Ontology (CL_ids).

    Returns: {cell_name: cl_id} for names that exist in CL. Names not in CL
             are silently dropped.
    """
    load_cell_ontology()
    result: Dict[str, str] = {}
    for name in cellmarker_celltypes:
        cl_id = cell_name_to_id(name)
        if cl_id is not None:
            result[name] = cl_id
    return result


def build_tissue_hierarchy(
    cell_names: List[str],
    max_depth: int = 4,
) -> str:
    """
    Build a compact text representation of how a set of cell types are
    related via the Cell Ontology hierarchy.

    Useful as context for the Hierarchical Feature LLM agent.

    Returns: A multi-line string showing each cell type with its 2-4
             closest ancestors. Example:

             CD8+ T cell  ← alpha-beta T cell ← T cell ← lymphocyte
             B cell       ← lymphocyte of B lineage ← lymphocyte
             Macrophage   ← mononuclear phagocyte ← myeloid leukocyte
    """
    lines = []
    for name in cell_names:
        chain = get_ancestor_chain(name, max_depth=max_depth)
        if not chain:
            lines.append(f"  {name}: (not found in Cell Ontology)")
            continue
        # chain[0] is the cell itself, rest are ancestors
        ancestor_names = [n for _, n in chain[1:]]
        if ancestor_names:
            lines.append(f"  {name}  ← " + " ← ".join(ancestor_names))
        else:
            lines.append(f"  {name}  (root)")
    return "\n".join(lines)


# Quick self-test
if __name__ == "__main__":
    print("Test: ancestor chains for PBMC cell types")
    for name in ["CD8-positive, alpha-beta T cell", "B cell", "macrophage",
                 "natural killer cell", "monocyte"]:
        chain = get_ancestor_chain(name)
        print(f"\n{name}:")
        for cl_id, n in chain:
            print(f"  {cl_id}: {n}")
