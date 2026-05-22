"""
ATLAS Pipeline
==============
Orchestrates agents to annotate a single cluster.

Two entry points:
  - annotate_cluster()      : Annotator → Validator → Formatter (3 agents)
  - annotate_cluster_full() : adds Scoring                       (4 agents)

Reporter (HTML output) is implemented separately in atlas/reports/.

Adapted from CASSIA's _run_analysis_logic in engine/main_function_code.py.
"""

import json
import re
from typing import Optional, Dict, Any, List, Tuple

from atlas.agents.base import Agent
from atlas.agents.scoring import score_annotation, format_conversation_for_scoring
from atlas.prompts.system_prompts import (
    ANNOTATOR_SYSTEM,
    VALIDATOR_SYSTEM,
    FORMATTER_SYSTEM,
    build_user_prompt,
)


# =============================================================================
# Helpers
# =============================================================================

def extract_json_from_reply(reply: str) -> Optional[dict]:
    """Pull a JSON object out of ```json ... ``` fences."""
    match = re.search(r'```json\s*\n(.*?)\n```', reply, re.DOTALL)
    if not match:
        print("⚠️ No ```json block found in formatter output.")
        return None
    try:
        return json.loads(match.group(1), strict=False)
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error: {e}")
        return None


# =============================================================================
# Annotator loop
# =============================================================================

def run_annotator(annotator: Agent, initial_prompt: str,
                  max_iter: int = 5) -> List[Tuple[str, str]]:
    """Run the Annotator until 'FINAL ANNOTATION COMPLETED' or max_iter."""
    convo = []
    prompt = initial_prompt
    for i in range(max_iter):
        reply = annotator(prompt, counterpart_id="user")
        convo.append(("Annotator", reply))
        if "FINAL ANNOTATION COMPLETED" in reply:
            break
        prompt = reply
    else:
        print(f"⚠️ Annotator hit max_iter={max_iter} without FINAL ANNOTATION COMPLETED")
    return convo


# =============================================================================
# Validator (one-shot)
# =============================================================================

def run_validator(validator: Agent, annotation_text: str,
                  marker_list: List[str], additional_info: str = "") -> str:
    """Send the annotation to the Validator; return its raw reply."""
    markers_str = ", ".join(marker_list)
    msg = f"""Please validate the following annotation result:

Annotation Result:
{annotation_text}

Context:

Marker List: {markers_str}
Additional Info: {additional_info or 'None'}

Validate the annotation based on this context.
"""
    return validator(msg, counterpart_id="annotator")


# =============================================================================
# Annotator ↔ Validator loop (up to 3 rounds, CASSIA-style feedback)
# =============================================================================

def annotate_with_validation(
    species: str,
    tissue: str,
    marker_list: List[str],
    additional_info: str = "",
    annotator_model: Optional[str] = None,
    validator_model: Optional[str] = None,
    max_validation_rounds: int = 3,
) -> Dict[str, Any]:
    """
    Run Annotator → Validator → (revise if failed) up to 3 times.

    CASSIA-style feedback message: includes previous response, validation
    feedback, AND the original prompt — gives Annotator full context to
    revise on.
    """
    initial_prompt = build_user_prompt(species, tissue, marker_list, additional_info)

    annotator = Agent(ANNOTATOR_SYSTEM, agent_name="annotation",
                      model=annotator_model, temperature=0.0)
    validator = Agent(VALIDATOR_SYSTEM, agent_name="validation",
                      model=validator_model, temperature=0.0)

    # First annotation pass
    convo = run_annotator(annotator, initial_prompt)
    annotation_text = convo[-1][1]  # last Annotator message

    val_reply = ""
    val_passed = False

    for round_i in range(max_validation_rounds):
        val_reply = run_validator(validator, annotation_text, marker_list, additional_info)
        convo.append(("Validator", val_reply))

        if "VALIDATION PASSED" in val_reply:
            val_passed = True
            break

        # CASSIA-style structured feedback to the Annotator
        feedback_msg = f"""Previous annotation attempt failed validation. Please review your previous response and the validation feedback, then provide an updated annotation:

Previous response:
{annotation_text}

Validation feedback:
{val_reply}

Original prompt:
{initial_prompt}

Please provide an updated annotation addressing the validation feedback."""

        revision = annotator(feedback_msg, counterpart_id="validator")
        convo.append(("Annotator (revision)", revision))
        annotation_text = revision

    return {
        "annotation_conversation": convo,
        "validation_passed": val_passed,
        "validation_reply": val_reply,
        "final_annotation_text": annotation_text,
        "initial_prompt": initial_prompt,
    }


# =============================================================================
# Formatter
# =============================================================================

def run_formatter(annotation_text: str,
                  model: Optional[str] = None) -> Tuple[Optional[dict], str]:
    """Returns (parsed_json_or_None, raw_reply)."""
    formatter = Agent(FORMATTER_SYSTEM, agent_name="formatting",
                      model=model, temperature=0.0)
    raw_reply = formatter(annotation_text, counterpart_id="user")
    parsed = extract_json_from_reply(raw_reply)
    return parsed, raw_reply


# =============================================================================
# Public entry points
# =============================================================================

def annotate_cluster(
    species: str,
    tissue: str,
    marker_list: List[str],
    additional_info: str = "",
    annotator_model: Optional[str] = None,
    validator_model: Optional[str] = None,
    formatter_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    3-agent pipeline: Annotator → Validator → Formatter.
    """
    val_result = annotate_with_validation(
        species=species,
        tissue=tissue,
        marker_list=marker_list,
        additional_info=additional_info,
        annotator_model=annotator_model,
        validator_model=validator_model,
    )

    structured, raw_format = run_formatter(
        val_result["final_annotation_text"],
        model=formatter_model,
    )

    # Append the Formatter turn to the conversation log
    val_result["annotation_conversation"].append(("Formatter", raw_format))

    return {
        "structured": structured,
        "annotation_text": val_result["final_annotation_text"],
        "validation_passed": val_result["validation_passed"],
        "validation_reply": val_result["validation_reply"],
        "conversation": val_result["annotation_conversation"],
    }


def annotate_cluster_full(
    species: str,
    tissue: str,
    marker_list: List[str],
    additional_info: str = "",
    annotator_model: Optional[str] = None,
    validator_model: Optional[str] = None,
    formatter_model: Optional[str] = None,
    scoring_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    4-agent pipeline: Annotator → Validator → Formatter → Scoring.

    This is the full ATLAS workflow (minus Reporter, which is non-LLM HTML).
    """
    # Steps 1-3
    result = annotate_cluster(
        species=species,
        tissue=tissue,
        marker_list=marker_list,
        additional_info=additional_info,
        annotator_model=annotator_model,
        validator_model=validator_model,
        formatter_model=formatter_model,
    )

    # Step 4: Score the whole thing
    history_str = format_conversation_for_scoring(result["conversation"])
    major_cluster_info = f"{species} {tissue}"
    if additional_info:
        major_cluster_info += f" — {additional_info}"

    score, score_reasoning = score_annotation(
        annotation_history=history_str,
        marker=", ".join(marker_list),
        major_cluster_info=major_cluster_info,
        model=scoring_model,
    )

    # Augment result
    result["score"] = score
    result["score_reasoning"] = score_reasoning
    result["score_flagged_low"] = (score is not None and score < 75)

    return result
