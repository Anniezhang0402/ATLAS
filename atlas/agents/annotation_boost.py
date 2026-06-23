"""
Annotation Boost Agent
======================================
定位：当某个 cluster 的注释不确定时调用，例如：
scoring 分数偏低、validator 多次未通过、亚型边界模糊、marker 基因存在矛盾等。

该 Agent 扮演“资深复核专家”，通过迭代假设生成精炼注释：
- breadth：一次提出多个竞争假设并行排查
- depth：锁定单一假设后逐步深入验证

核心机制：
- LLM 在分析中使用 <check_genes>GENE1,GENE2</check_genes> 标签，提出需要进一步检查表达的基因
- 执行层根据这些基因查询表达信息
- LLM 基于新证据继续分析，直到完成最终注释或达到最大迭代次数
"""

import re
from typing import Callable, Dict, List, Optional, Tuple

from ..core.agent import Agent


BOOST_HYPOTHESIS_PROMPT = """
You are a careful senior computational biologist called in whenever an annotation needs deeper scrutiny, disambiguation, or simply a second opinion. Your job is to (1) assess the current annotation's robustness and (2) propose up to three decisive follow-up checks that the executor can run, such as examining the expression of key positive or negative markers. You should be skeptical, evidence-based, and avoid rushing to conclusions.

Context Provided to You:

Cluster summary:
{major_cluster_info}

Top ranked markers (high → low):
{comma_separated_genes}

Prior annotation results:
{annotation_history}

What you should do:

1. Brief Evaluation - One concise paragraph that:
    - Highlights strengths, ambiguities, or contradictions in the current call.
    - Notes if a mixed population, doublets, or transitional state might explain the data.

2. Design up to 3 follow-up checks (cell types or biological hypotheses):

    - When listing genes for follow-up checks, use the <check_genes>...</check_genes> tags.
    - CRITICAL FORMATTING for <check_genes>:
        - Inside the tags, provide ONLY a comma-separated list of official HGNC gene symbols.
        - Example: <check_genes>GENE1,GENE2,GENE3</check_genes>
        - Do not include extra spaces, newlines, numbering, or commentary inside the tags.
        - Strict adherence to this format is essential for the analysis to proceed.
    - Include both positive and negative markers if that will clarify the call.
    - Include reasoning: explain why these genes are useful and what pattern would confirm or refute the hypothesis.

3. Upon receiving gene expression results, further your analysis based on the current analysis. Generate new hypotheses if necessary. Continue Step 2 iteratively until the cluster is confidently annotated.

Once finalized, output the single line:

FINAL ANNOTATION COMPLETED

Then provide a conclusion paragraph that includes:

1. The final cell type
2. Confidence level: high, medium, or low
3. Key markers supporting your conclusion
4. Alternative possibilities only if confidence is not high, and what should be checked next

Output Template:

Evaluation
[One short paragraph]

celltype to check 1

<check_genes>GENE1,GENE2,GENE3</check_genes>

<reasoning>
Why these genes and what we expect to see.
</reasoning>

celltype to check 2

<check_genes>GENE4,GENE5</check_genes>

<reasoning>
...
</reasoning>

hypothesis to check 3

<check_genes>GENE6,GENE7</check_genes>

<reasoning>
...
</reasoning>

Use "hypothesis to check n" instead of "celltype to check n" when proposing non-canonical possibilities, such as a cycling subpopulation or doublet.

Provide no more than three total blocks, including cell types and hypotheses.

For each hypothesis check, include no more than seven genes.

If marker information is insufficient to make a conclusion, explicitly inform the user and end the analysis.

Tone & Style Guidelines:

- Skeptical, critical, and careful
- Professional, succinct, and evidence-based
- Progressively deepen the analysis
- Do not repeat the same hypothesis without new evidence
"""


def extract_check_genes(text: str) -> List[str]:
    match = re.search(
        r"<check_genes>(.*?)</check_genes>",
        text,
        re.DOTALL,
    )

    if not match:
        return []

    genes_text = match.group(1)

    return [
        gene.strip()
        for gene in genes_text.split(",")
        if gene.strip()
    ]


def run_annotation_boost(
    major_cluster_info: str,
    comma_separated_genes: str,
    annotation_history: str,
    gene_expression_lookup: Optional[Callable[[List[str]], str]] = None,
    num_iterations: int = 3,
    model: Optional[str] = None,
    provider: str = "openrouter",
    temperature: float = 0,
) -> Tuple[str, List[Dict[str, str]]]:
    """
    运行迭代式 Annotation Boost 流程。
    """

    boost_agent = Agent(
        system="",
        model=model,
        temperature=temperature,
        provider=provider,
    )

    prompt = BOOST_HYPOTHESIS_PROMPT.format(
        major_cluster_info=major_cluster_info,
        comma_separated_genes=comma_separated_genes,
        annotation_history=annotation_history,
    )

    completion_marker = "FINAL ANNOTATION COMPLETED"

    messages: List[Dict[str, str]] = []

    final = ""

    for iteration in range(num_iterations):
        response = boost_agent(
            prompt,
            conversation_id="boost",
        )

        messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        final = response

        if completion_marker in response:
            break

        check_genes = extract_check_genes(response)

        if not check_genes:
            prompt = (
                "No further gene checks were requested. "
                "Please finalize the annotation using the available evidence. "
                "Include the exact line: FINAL ANNOTATION COMPLETED"
            )
            continue

        if gene_expression_lookup:
            expr_info = gene_expression_lookup(check_genes)

        else:
            expr_info = (
                f"Expression data for requested genes "
                f"({', '.join(check_genes)}) is not available in this run. "
                f"Reason from the existing marker list, tissue context, "
                f"and prior biological knowledge. Finalize if possible."
            )

        prompt = (
            f"Gene expression results:\n"
            f"{expr_info}\n\n"
            f"Continue your analysis. If the annotation is sufficiently supported, "
            f"output: FINAL ANNOTATION COMPLETED"
        )

    return final, messages