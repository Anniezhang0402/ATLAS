"""
ATLAS Scoring Agent
===================
Evaluates an annotation conversation, returns (score 0-100, reasoning).

Design notes:
  - Not a long-lived Agent. Just a stateless function calling LLM once.
  - Output uses XML-style tags (<score>, <reasoning>) - more robust than JSON because reasoning is long free-text.
  - 7 regex fallbacks for the score so a misbehaving LLM still parses.
  - Default model is cheap (DeepSeek v3) -scoring is simpler than annotation.
"""

import re
from typing import Optional, Tuple, List
from atlas.llm_client import call_llm

# -------------------Prompt
def build_scoring_prompt(major_cluster_info: str,
                         marker: str,
                         annotation_history: str) -> str:
    """
    Build the scoring prompt.

    Args:
        major_cluster_info: Free text like "Human PBMC, healthy donor".
        marker: Comma-seperated marker list (string, not list).
        annotation_history: Formatted conversation history(see format_conversation_for_scoring below).
    """
    return f"""
You are an expert in single-cell annotation analysis. Your task is to evaluate and rate single-cell annotation results, focusing on their correctness and ability to capture the overall picture of the data. You will be provided a score from 0 to 100 and justify your rating.

Here are the single-cell annotation results to evaluate:

<marker>
{marker}
</marker>

<Cluster Origin>
{major_cluster_info}
</Cluster Origin>

<annotation_history>
{annotation_history}
</annotation_history>

Caredully analyze these results, paying particular attention to the following aspects:
1. Correctness of the annotations
2. Balanced consideration of multiple markers rather than over-focusing on a specific one
3. Ability to capture the general picture of the cell populations

When evaluating, consider:
- Are the annotations scientifically accurate?
- Is there a good balance in the use of different markers?
- Dose the annotation provide a comprehensive view of the cell types present?
- Are there any obvious misclassifications or oversights?
- Did it consider the rank of the matter? Marker appearing first is more important.

Provide your analysis in the following format:
1. Start with a <reasoning> tag, where you explain your evaluation of the annotation results. Discuss the strengths and weaknesses you've identified, referring to a specific examples from the results where possible.
2. After your reasoning, use a <score> tag to provide a numerical score from 0 to 100, where 0 represents completely incorrect or unusable results, and 100 represents perfect annotation that captures all aspects of the data correctly.

Your response should look like this:

<reasoning>
[Your detailed analysis and justification here]
</reasoning>

<score>[Your numerical score between 0 and 100]</score>

Remember, the focus is on correctness and the ability to see the general picture, rather than the structure of the results. Be critical but fair in your assessment.
""".strip()

# -------------------Output parser 9robust, 7-way fallback

#try patterns in order; the first match wins.
_SCORE_PATTERNS = [
    r'<score>\s*(\d{1,3})\s*</score>',  # canonical
    r'Score:\s*(\d{1,3})',
    r'score:\s*(\d{1,3})',
    r'(\d{1,3})\s*/\s*100',
    r'(\d{1,3})\s*out\s*of\s*100',
    r'rating[^0-9]{0,20}(\d{1,3})',
    r'(\d{1,3})\s*%',
]

_REASONING_PATTERNS = [
    r'<reasoning>(.*?)</reasoning>',
    r'Reasoning:\s*(.*?)(?=Score:|$)',
    r'reasoning:\s*(.*?)(?=score:|$)',
    r'Analysis:\s*(.*?)(?=Score:|$)',
    r'Evaluation:\s*(.*?)(?=Score:|$)',
]

def extract_score_and_reasoning(text:str) -> Tuple[Optional[int], Optional[str]]:
    """
    Pull a 0-100 score and a reasoning string out of LLM output.
 
    Returns (None, None) if score can't be found. Reasoning falls back to the whole text if no tag matches.
    """
    score: Optional[int] = None
    reasoning: Optional[str] = None

    for pat in _SCORE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 0<= val <= 100:
                    score = val
                    break
            except ValueError:
                continue
    for pat in _REASONING_PATTERNS:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            reasoning = m.group(1).strip()
            break

    if reasoning is None and text.strip():
        reasoning = text.strip()

    return score, reasoning

# ----------------- Format conversation history for scoring
def format_conversation_for_scoring(
    conversation: List[Tuple[str, str]],
) -> str:
    """
    Turn ATLAS pipeline's [(speaker, msg), ...] into the labeled string format that the Scoring prompt expects.

    Annotator turns becomes "Annotation Attept N", Validator turns become "Validation N", anything else is labeled by its speaker name.
    """
    parts = []
    ann_idx = 0
    val_idx = 0
    for speaker, msg in conversation:
        if "Annotator" in speaker:
            ann_idx += 1
            parts.append(f"=== Annotation Attempt {ann_idx} ===\n{msg}")
        elif "Validator" in speaker:
            val_idx += 1
            parts.append(f"=== Validation {val_idx} ===\n{msg}")
        else:
            parts.append(f"=== {speaker} ===\n{msg}")
    return "\n\n".join(parts)

# -----------------Main entry point
def score_annotation(
    annotation_history: str,
    marker: str,
    major_cluster_info: str,
    model: Optional[str] = None,
    temperature: float=0.0,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Score an annotation. One LLM call. No state.

    Args:
        annotation_history: Formatted conversation history string (use format_conversation_for_scoring() to build it.)
        marker: Comma-seperated marker list (string).
        major_cluster_info: Free-text context like "Human PBMC".
        model: Override default ("deepseek/deepseek-chat-v3-0324").
        temperature: 0.0 for deterministic scores.

    Returns:
        (score, reasoning) - score is int 0-100 or None if parse failed.
    """
    prompt = build_scoring_prompt(major_cluster_info, marker, annotation_history)

    response = call_llm(
        user_prompt=prompt,
        agent="scoring",
        model=model,
        temperature=temperature,
        max_tokens=4096,
    )

    return extract_score_and_reasoning(response)
        
