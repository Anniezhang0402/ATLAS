"""
ScRAG Agent
========================================

Wraps hybrid retrieval with knowledge graph and vector search as an agent.

This agent provides external biological grounding before or during annotation.
It can either generate an evidence-grounded cell type prediction directly or
return retrieved evidence for the main annotation agent to use.
"""

from typing import Optional
from ..core.agent import Agent 
from ..retrieval.hybrid_retriever import HybridRetriever 

_SCRAG_ANSWER_TEMPLATE = """Answer the question based only on the following context:

{context}

Question: {question}

Use natural language and be concise.

Answer:"""

class ScRAGAgent:
    """
    Retrieval-augmented agent for cell type annotation.

    The agent supports two usage modes:

    1. predict():
       Reetrieve evidence and generate a direct cell type prediction.

    2. retrieve_evidence():
       Returen retrieved evidence only, allowing the main Annotator to 
       incorporate the evidence into its own reasoning process.
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        model: Optional[str] = None,
        provider: str = "openrouter",
        temperature: float = 0,
    ):

        self.retriever = retriever 

        self.llm = Agent(
            system="",
            model=model,
            temperature=temperature,
            provider=provider,
        )

    def retrieve_evidence(self, question: str) -> str:
        """
        Retrieve hybrid biological evidence without generating a prediction.

        Args:
            question: A cell annotation query containing tissue and marker genes.

        Returns:
            A combined context string containing graph-based and vector-based evidence.
        """
        return self.retriever.retrieve(question)

    def predict(self, question: str) -> str:
        """
        Retrieve evidence and generate an evidence-grounded cell type prediction.

        Args:
            question: A cell annotation query containing tissue and marker genes.

        Returns:
            A concise LLM-generated prediction based only on retrieved evidence.
        """

        context = self.retriever.retrieve(question)

        prompt = _SCRAG_ANSWER_TEMPLATE.format(
            context=context,
            question=question,
        )
        
        return self.llm(
            prompt,
            conversation_id="scrag_predict",
        )

    @staticmethod
    def build_query(tissue: str, top_genes: list) -> str:
        """
        Build a retrieval query from tissue context and ranked marker genes.

        Args:
            tissue: The tissue of origin.
            top_genes: A ranked list of highly expressed marker genes.

        Returns:
            A natural-language query for hybrid retrieval.
        """

        genes = ', '.join(top_genes)
        return (
            f"Task: Given the following information about a cell, predict its most "
            f"likely cell type. Tissue: {tissue}. "
            f"Top genes for this cell (highest expression first): {genes}."
        )
    