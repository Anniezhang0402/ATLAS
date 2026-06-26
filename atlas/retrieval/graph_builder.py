"""
scRAG Knowledge Graph Builder
=================================================================

Responsibilities:
   1. Read corpus -> split into chunks
   2. Use an LLM to automatically extract a knowledge graph text chuncks,
   then write it into Neo4j via LLMGraphTransformer
   3. Build a vector index on the graph
   4. Build an entity full-text index for fuzzy entity matching during retrieval
   5. Provide an entity extractor
"""

import os
import re
import json
import time
from typing import List, Callable

from ..core.agent import Agent 

def build_graph_from_corpus(
    corpus_path: str,
    graph,
    llm_model: str = "gpt-4o",
    provider: str = "openai",
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    batch_size: int = 10,
):
    """
    Read corpus → split text → build graph with LLM → write into Neo4j.
    
    Args:
        corpus_path: Path to the training corpus text file
        corpus_path: Path to the training corpus text file
        graph:       Neo4jGraph instance
        llm_model:   LLM used for graph construction
                     The original version used gpt-4-turbo;
                     here the default is gpt-4o
        provider:    LLM provider
    """

    from langchain_community.document_loaders import TextLoader
    from langchain.text_splitter import CharacterTextSplitter
    from langchain_openai import ChatOpenAI
    from langchain_experimental.graph_transformers import LLMGraphTransformer
    from neo4j.exceptions import ServiceUnavailable

    documents = TextLoader(corpus_path).load()

    splitter = CharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = splitter.split_documents(documents)
    print(f"Chunking completed: {len(chunks)} chunks created.")

    llm = ChatOpenAI(temperature=0, model_name=llm_model)
    transformer = LLMGraphTransformer(llm=llm)

    def process_batch(batch, retries=3):
        for attempt in range(retries):
            try:
                graph_docs = transformer.convert_to_graph_documents(batch)

                graph.add_graph_documents(
                    graph_docs,
                    baseEntityLabel=True,
                    include_source=True
                )
                return

            except ServiceUnavailable as e:
                print(f"Neo4j is temporarily unavailable. Retry {attempt + 1}/{retries}: {e}")
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    raise

    for i in range(0, len(chunks), batch_size):
        process_batch(chunks[i:i + batch_size])
        print(f"Processed {min(i + batch_size, len(chunks))}/{len(chunks)} chunks.")


def build_vector_index(embeddings=None):
    from langchain_community.vectorstores import Neo4jVector
    from langchain_openai import OpenAIEmbeddings

    return Neo4jVector.from_existing_graph(
        embeddings or OpenAIEmbeddings(),
        search_type="hybrid",
        node_label="Document",
        text_node_properties=["text"],
        embedding_node_property="embedding",
    )


def create_entity_fulltext_index(graph):
    graph.query(
        "CREATE FULLTEXT INDEX entity IF NOT EXISTS "
        "FOR (e:__Entity__) ON EACH [e.id]"
    )


def make_entity_extractor(
    model: str = "gpt-4o",
    provider: str = "openai"
) -> Callable[[str], List[str]]:

    system = (
        "You are extracting Tissue and gene entities from single-cell annotation queries. "
        "Return ONLY a JSON array of entity name strings (tissue names and gene symbols), "
        "no prose, no markdown. Example: [\"heart\", \"RYR2\", \"TTN\"]"
    )

    extractor_agent = Agent(
        system=system,
        model=model,
        temperature=0,
        provider=provider
    )

    def extract(question: str) -> List[str]:
        reply = extractor_agent(
            question,
            conversation_id=f"extract_{hash(question)}"
        )

        m = re.search(r'\[.*\]', reply, re.DOTALL)

        if m:
            try:
                names = json.loads(m.group(0))
                return [
                    str(n).strip()
                    for n in names
                    if str(n).strip()
                ]
            except json.JSONDecodeError:
                pass

        return [
            w.strip()
            for w in re.split(r'[,\n]', reply)
            if w.strip()
        ][:20]

    return extract