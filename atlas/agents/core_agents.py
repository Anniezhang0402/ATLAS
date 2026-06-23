````python
"""
ATLAS core annotation workflow.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from ..core.agent import Agent
from . import prompts


def extract_json_from_reply(reply: str) -> Optional[dict]:
    m = re.search(r"```json\n(.*?)\n```", reply, re.DOTALL)

    if m:
        try:
            return json.loads(m.group(1), strict=False)
        except json.JSONDecodeError as e:
            print(f"Parsing failed: {e}")
    else:
        print("No JSON content found in the response")

    return None


def construct_prompt(
    species: str,
    tissue: Optional[str],
    marker_list: List[str],
    additional_info: str = "",
) -> str:
    markers = ", ".join(marker_list)

    prompt = f"Your task is to annotate a single-cell {species} dataset"

    if tissue and tissue.lower() not in ["none", "tissue blind"]:
        prompt += f" from {tissue} tissue"

    prompt += f". Please identify the cell type based on this ranked marker list:\n{markers}"

    if additional_info and additional_info.lower() != "no":
        prompt += f" Additional information about the dataset:\n{additional_info}."

    return prompt


def run_annotator(
    agent: Agent,
    prompt: str,
    max_iterations: int = 5,
) -> List[Tuple[str, str]]:
    conversation: List[Tuple[str, str]] = []

    for _ in range(max_iterations):
        response = agent(prompt, "annotator")
        conversation.append(("Annotator", response))

        if "FINAL ANNOTATION COMPLETED" in response:
            break

        prompt = response

    return conversation


def run_validator(
    agent: Agent,
    annotation_result: str,
    marker_list: List[str],
    additional_info: str = "",
) -> str:
    marker_str = ", ".join(marker_list)

    message = f"""Please validate the following annotation result:

Annotation Result:
{annotation_result}

Context:

Marker List: {marker_str}
Additional Info: {additional_info or 'None'}

Validate the annotation based on this context.
"""

    return agent(message, "validator")


def run_formatter(
    agent: Agent,
    final_annotations: List[Tuple[str, str]],
) -> str:
    text = "\n\n".join([msg[1] for msg in final_annotations])
    return agent(text, "formatter")


def extract_score_and_reasoning(text: str) -> Tuple[Optional[int], Optional[str]]:
    score = None
    reasoning = None

    for pattern in [
        r"<score>(\d+)</score>",
        r"Score:\s*(\d+)",
        r"(\d+)/100",
        r"(\d+)%",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            break

    match = re.search(
        r"<reasoning>(.*?)</reasoning>",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if match:
        reasoning = match.group(1).strip()
    elif text.strip():
        reasoning = text.strip()

    return score, reasoning


def run_scoring(
    species: str,
    tissue: Optional[str],
    marker_list: List[str],
    annotation_history: str,
    model: Optional[str] = None,
    provider: str = "openrouter",
) -> Tuple[Optional[int], Optional[str]]:
    cluster_info = f"Species: {species}; Tissue: {tissue or 'unknown'}"
    marker_str = ", ".join(marker_list)

    prompt = prompts.SCORING_PROMPT_TEMPLATE.format(
        marker=marker_str,
        major_cluster_info=cluster_info,
        annotation_history=annotation_history,
    )

    scorer = Agent(
        system="",
        model=model,
        temperature=0,
        provider=provider,
    )

    reply = scorer(prompt, "scoring")

    return extract_score_and_reasoning(reply)


def build_report(
    result: Dict[str, Any],
    conversation: List[Tuple[str, str]],
    score: Optional[int],
    reasoning: Optional[str],
) -> str:
    lines = ["# ATLAS Cell Type Annotation Report\n"]

    lines.append(f"**Primary Cell Type**: {result.get('main_cell_type', 'N/A')}\n")

    subs = result.get("sub_cell_types", [])
    if subs:
        lines.append(f"**Candidate Subtypes**: {', '.join(subs)}\n")

    mixed = result.get("possible_mixed_cell_types", [])
    if mixed:
        lines.append(f"**Potential Mixed Cell Types**: {', '.join(mixed)}\n")

    tissues = result.get("possible_tissues", [])
    if tissues:
        lines.append(f"**Inferred Tissues**: {', '.join(tissues)}\n")

    if score is not None:
        lines.append(f"\n**Quality Score**: {score}/100\n")

    if reasoning:
        lines.append(f"\n**Scoring Rationale**:\n\n{reasoning}\n")

    lines.append(f"\n**Iteration Count**: {result.get('iterations', 'N/A')}  ")
    lines.append(f"**Number of Markers**: {result.get('num_markers', 'N/A')}\n")

    lines.append("\n---\n\n## Full Reasoning Trace\n")

    for role, msg in conversation:
        lines.append(f"\n### {role}\n\n{msg}\n")

    return "\n".join(lines)


def run_core_annotation(
    marker_list: List[str],
    tissue: Optional[str],
    species: str,
    model: Optional[str] = None,
    provider: str = "openrouter",
    temperature: float = 0,
    additional_info: str = "",
    validator_version: str = "v1",
    max_validation_rounds: int = 3,
    score: bool = True,
) -> Tuple[Optional[dict], List[Tuple[str, str]], Optional[str]]:
    is_tissue_blind = (not tissue) or tissue.lower() in ["none", "tissue blind"]

    annotator_sys = (
        prompts.ANNOTATOR_SYSTEM_TISSUE_BLIND
        if is_tissue_blind
        else prompts.ANNOTATOR_SYSTEM_KNOWN_TISSUE
    )

    if validator_version == "v0":
        validator_sys = prompts.VALIDATOR_SYSTEM_V0
    else:
        validator_sys = (
            prompts.VALIDATOR_SYSTEM_TISSUE_BLIND
            if is_tissue_blind
            else prompts.VALIDATOR_SYSTEM_KNOWN_TISSUE
        )

    annotator = Agent(
        system=annotator_sys,
        model=model,
        temperature=temperature,
        provider=provider,
    )

    validator = Agent(
        system=validator_sys,
        model=model,
        temperature=temperature,
        provider=provider,
    )

    formatter = Agent(
        system="",
        model=model,
        temperature=temperature,
        provider=provider,
    )

    base_prompt = construct_prompt(
        species=species,
        tissue=tissue,
        marker_list=marker_list,
        additional_info=additional_info,
    )

    full_history: List[Tuple[str, str]] = []
    annotation_conv: List[Tuple[str, str]] = []
    validation_result = ""
    passed = False
    rnd = 0

    while not passed and rnd < max_validation_rounds:
        rnd += 1
        current = base_prompt

        if rnd > 1:
            current = (
                "Previous annotation failed validation. Review your previous "
                "response and the feedback, then provide an updated annotation:\n\n"
                f"Previous response:\n{annotation_conv[-1][1]}\n\n"
                f"Validation feedback:\n{validation_result}\n\n"
                f"Original prompt:\n{base_prompt}\n\n"
                "Provide an updated annotation."
            )

        annotation_conv = run_annotator(
            agent=annotator,
            prompt=current,
        )

        full_history.extend(annotation_conv)

        validation_result = run_validator(
            agent=validator,
            annotation_result=annotation_conv[-1][1],
            marker_list=marker_list,
            additional_info=additional_info,
        )

        full_history.append(("Validator", validation_result))

        if "VALIDATION PASSED" in validation_result:
            passed = True

    if passed:
        formatter.system = (
            prompts.FORMATTER_SYSTEM_TISSUE_BLIND
            if is_tissue_blind
            else prompts.FORMATTER_SYSTEM_KNOWN_TISSUE
        )
    else:
        formatter.system = prompts.FORMATTER_SYSTEM_FAILED

    raw = run_formatter(
        agent=formatter,
        final_annotations=annotation_conv[-2:],
    )

    full_history.append(("Formatter", raw))

    result = extract_json_from_reply(raw)

    sc, reasoning = (None, None)

    if score and result is not None:
        history_text = "\n\n".join([message[1] for message in annotation_conv])

        sc, reasoning = run_scoring(
            species=species,
            tissue=tissue,
            marker_list=marker_list,
            annotation_history=history_text,
            model=model,
            provider=provider,
        )

    report = None

    if result is not None:
        result["iterations"] = rnd
        result["num_markers"] = len(marker_list)
        result["validation_passed"] = passed
        result["score"] = sc

        report = build_report(
            result=result,
            conversation=full_history,
            score=sc,
            reasoning=reasoning,
        )

    return result, full_history, report
````
