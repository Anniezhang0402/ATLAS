"""
ATLAS Pipeline(minimal version)
===============================
Runs Annotator -> Validator -> formatter for a single cluster.

This is the "engine" that orchestrates the agents. Scoring+reporter will be added next.

Adapted from CASSIA's _run_analysis_logic in engine/main_function_code.py.
"""

import json
import re
from typing import Optional, Dict, Any, List, Tuple

from atlas.agents.base import Agent
from atlas.prompts.system_prompts import(
    ANNOTATOR_SYSTEM,
    VALIDATOR_SYSTEM,
    FORMATTER_SYSTEM,
    build_user_prompt,
)

# ---------------Helper: extract JSON from a fenced block---------
def extract_json_from_reply(reply: str) -> Optional[dict]:
    """
    Pull a JSON object out of ```json ... ``` fences.
    Mirrors ATLAS's extract_json_from_reply, with strict=False to tolerate
    """
    match = re.search(r'```json\s*\n(.*?)\n```', reply, re.DOTALL)

    if not match:
        print("⚠️ No ```json block found in formatter output.")
        return None

    try:
        return json.loads(match.group(1), strict=False)
    
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error: {e}")
        return None

# ----------------Annotator loop (with FINAL ANNOTATION COMPLETED)
def run_annotator(annotator: Agent, initial_prompt: str,
                  max_iter: int=5) -> List[Tuple[str,str]]:
##run_annotator最多循环五次

    """
    Run the Annotator until it says "FINAL ANNOTATION COMPLETED" or hits max_iter.
    Returns a list of (speaker,message) tuples for the full conversation.
    """

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

# ----------------Validator: one-shot validation
def run_validator(validator: Agent, annotation_text: str,
                  marker_list: List[str], additional_info: str = "") -> str:
    """
    Ask the validator to check the Annotator's output.
    returns the validator's raw reply (contains 'VALIDATION PASSED' or 'VALIDATION FAILED')
    """
    markers_str = ", ".join(marker_list)
    msg = f"""Please validate the following annotation result:

Annotation Result:
{annotation_text}

Context:

Marker List:{markers_str}
Additional Info: {additional_info or 'None'}

Validate the annotation based on this context.
"""
    return validator(msg, counterpart_id="annotator")

# --------------Validation loop(Annotator ↔ Validator, up to 3 cycles)
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
    Full Annotator ↔ Validator loop.

    Returns a dict with:
    - 'annotation_conversation': list of (speaker, message)
    - 'validation_passed': bool
    - 'validation_reply': str
    - 'final_annotation_text': str (concatenated Annotator outputs)
    """
    # 1. Build initail prompt
    initial_prompt = build_user_prompt(species, tissue, marker_list, additional_info)
    
    # 2. Instantiate agents
    annotator = Agent(ANNOTATOR_SYSTEM, agent_name="annotation",
                      model=annotator_model, temperature=0.0)
    validator = Agent(VALIDATOR_SYSTEM, agent_name="validation",
                      model=validator_model, temperature=0.0)
        

    convo = run_annotator(annotator, initial_prompt)
    annotation_text = "\n\n".join(msg for _, msg in convo)

    #3. validation loop
    val_reply = ""
    val_passed = False

    for round_i in range(max_validation_rounds):
        val_reply = run_validator(validator, annotation_text, marker_list, additional_info)
        convo.append(("Validator", val_reply))
        if "VALIDATION PASSED" in val_reply:
            val_passed = True
            break
        feedback_msg = (
            f"The validator returned feedback: \n\n{val_reply}\n\n"
            f"Please revise your annotation accordingly."
        )
        revision = annotator(feedback_msg, counterpart_id="validator")
        convo.append(("Annotator(revision)", revision))
        annotation_text = revision

    return {
        "annotation_conversation": convo,
        "validation_passed": val_passed,
        "validation_reply": val_reply,
        "final_annotation_text": annotation_text,
    }

# --------------------Format Step
def run_formatter(annotation_text: str,
                  model: Optional[str] = None) -> Optional[dict]:
    """Convert raw annotation text into structured JSON."""
    formatter = Agent(FORMATTER_SYSTEM, agent_name="formatting",
                      model=model, temperature = 0.0)
    raw_reply = formatter(annotation_text, counterpart_id="user")
    return extract_json_from_reply(raw_reply)

#---------------Public top-level entry point
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
    The one function you call from outside. Runs Annotator → Validator → Formatter.

    Returns:
    {
      'structured': {...},        # JSON-extracted main_cell_type, sub_cell_types, ...
      'annotation_text': str,     #raw Annotator output
      'validation_passed': bool,
      'validation_reply': str,
      'conversation': [(speaker, msg), ...]
      }
    """
    val_result = annotate_with_validation(
        species=species,
        tissue=tissue,
        marker_list=marker_list,
        additional_info=additional_info,
        annotator_model=annotator_model,
        validator_model=validator_model,
    )

    structured = run_formatter(
        val_result["final_annotation_text"],
        model=formatter_model,
    )

    return {
        "structured": structured,
        "annotation_text": val_result["final_annotation_text"],
        "validation_passed": val_result["validation_passed"],
        "validation_reply": val_result["validation_reply"],
        "conversation": val_result["annotation_conversation"],
    }
        
