"""
scRAG Hybrid Retriever
=================================================================
It retrieves two types of evidence:

1. Structured route:
   Retrieve neighboring entity relations from the knowledge graph(Neo4j),
   such as:
      gene -EXPRESSED_IN-> cell type
      cell type -LOCATED_IN-> tissue

2. Unstructured route:
   Retrieve semantically similar documents from the vector index.
"""
from typing import List
from collections import defaultdict

class HybridRetriever:

    def __init__(self, graph, vector_index, entity_extractor):
        """
        Args:
            graph: Neo4jGraph instance
            vector_index: Neo4jVector instance for hybrid search
            entity_extractor: Callable objects that extracts tissue and gene entities from a quesion
        """
        self.graph = graph
        self.vector_index = vector_index
        self.entity_extractor = entity_extractor 

    @staticmethod
    def _generate_full_text_query(text: str) -> str:
        """
        Construct a fault-tolerant full-text query.

        For each word, the query allows about two characters of spelling error
        and connects the words with AND, making it easier to map entity names
        from the question to graph nodes.
        """
        from langchain_community.vectorstores.neo4j_vector import remove_lucene_chars
        
        words = [w for w in remove_lucene_chars(text).split() if w]

        if not words:
            return ""

        query = " ".join(f"{w} AND" for w in words[:-1])
        return (query + f" {words[-1]}").strip()

def structured_retrieve(self, question: str) -> str:

    entities = self.entity_extractor(question)

    results = []

    for entity in entities:

        query_str = self._generate_full_text_query(entity)

        if not query_str:
            continue

        response = self.graph.query(
            """CALL db.index.fulltext.queryNodes('entity', $query, {limit:2})
                YIELD node, score
                CALL {
                  WITH node
                  MATCH (node)-[r:!MENTIONS]->(neighbor)
                  RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
                  UNION ALL
                  WITH node
                  MATCH (node)<-[r:!MENTIONS]-(neighbor)
                  RETURN neighbor.id + ' - ' + type(r) + ' -> ' + node.id AS output
                }
                RETURN output LIMIT 50""",
                {"query": query_str},
        )

        results.extend([el["output"] for el in response])
    
    return "\n".join(results)

@staticmethod
def merge_structured_data(structured_data: str) -> str:

    lines = structured_data.strip().split('\n')

    merged_located = defaultdict(list)
    merged_expressed = defaultdict(list)

    for line in lines:
        line = line.strip()

        if "LOCATED_IN" in line:
            try:
                key, value = line.split(' - LOCATED_IN')
                merged_located[value.strip()].append(key.strip())
            except ValueError:
                continue

        elif "EXPRESSED_IN" in line:
            try:
                key, value = line.split('->')
                merged_expressed[key.strip()].append(value.strip())
            except ValueError:
                continue

    out = []

    for value, keys in merged_located.items():
        out.append(f"{', '.join(set(keys))} - LOCATED_IN {value}")

    for key, values in merged_expressed.items():
        out.append(f"{key} -> {', '.join(set(values))}")

    return '\n'.join(out)

def unstructured_retrieve(self, question: str, k: int = 4) -> List[str]:
    
    docs = self.vector_index.similarity_search(question, k=k)
    return [d.page_content for d in docs]

def retrieve(self, question: str) -> str:

    structured = self.merge_structured_data(
        self.structured_retrieve(question)
    )

    unstructured = self.unstructured_retrieve(question, k=4)

    return f"""Structured data:
{structured}
Unstructured data:
{"#Document ".join(unstructured)}
"""