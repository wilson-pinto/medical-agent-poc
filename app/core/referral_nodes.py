# app/core/referral_nodes.py
import json
import os
from typing import Dict, Any, Optional, Callable
from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ----------------------------
# Load referral rules from JSON
# ----------------------------
RULES_PATH = os.getenv("REFERRAL_RULES_PATH", "data/referral_rules.json")

try:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        REFERRAL_RULES = json.load(f)
    logger.info(f"[REFERRAL_NODE] Loaded {len(REFERRAL_RULES)} referral rules.")
except Exception as e:
    logger.error(f"[REFERRAL_NODE] Failed to load referral rules: {e}")
    REFERRAL_RULES = []

# ----------------------------
# Helper: find matching rules
# ----------------------------
def find_matching_rule(soap_text: str) -> Optional[Dict[str, Any]]:
    """
    Returns the first rule that matches any keyword in the SOAP text.
    """
    text_lower = soap_text.lower()
    for rule in REFERRAL_RULES:
        keywords = rule.get("keywords", [])
        if any(kw.lower() in text_lower for kw in keywords):
            return rule
    return None

# ----------------------------
# Execute Referral Node
# ----------------------------
async def execute_referral_node(
    state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """
    Node that executes the referral decision if required.
    Logs whether the referral was triggered by code or SOAP text.
    """
    from app.core.referral_nodes import find_matching_rule

    logger.info(f"[REFERRAL_NODE] Evaluating referral for session {state.session_id}")
    applied_rule = find_matching_rule(state.soap_text)

    updates: Dict[str, Any] = {}
    triggered_by = None

    if applied_rule and applied_rule.get("referral_required", False):
        updates["referral_rule_applied"] = applied_rule.get("id")
        updates["referral_required"] = True
        reasoning = f"Matched rule {applied_rule.get('id')}: {applied_rule.get('description')}"
        triggered_by = "SOAP text"
    else:
        # fallback: check predicted codes
        code_triggered = any(sc.code.startswith("FRACT") for sc in getattr(state, "predicted_service_codes", []))
        updates["referral_required"] = code_triggered
        updates["referral_rule_applied"] = applied_rule.get("id") if applied_rule else None
        triggered_by = "Predicted service code" if code_triggered else None
        reasoning = f"Referral triggered by: {triggered_by}" if triggered_by else "No referral required."

    # Update reasoning trail
    reasoning_trail = getattr(state, "reasoning_trail", [])
    reasoning_trail.append(reasoning)
    updates["reasoning_trail"] = reasoning_trail

    # Append StageEvent
    stages = getattr(state, "stages", [])
    stages.append(StageEvent(
        code="execute_referral",
        description="Referral node executed",
        data={
            "reasoning": reasoning,
            "applied_rule": updates["referral_rule_applied"],
            "triggered_by": triggered_by
        }
    ))
    updates["stages"] = stages

    # Send WebSocket update
    if ws_send:
        try:
            await ws_send({
                "event_type": "node_update",
                "node": "execute_referral",
                "payload": state.model_copy(update=updates).dict()
            })
        except Exception as e:
            logger.error(f"[REFERRAL_NODE] Failed sending ws update: {e}")

    return updates


# ----------------------------
# Check Referral Required Node
# ----------------------------
# ----------------------------
# Check Referral Required Node (Refined)
# ----------------------------
async def check_referral_required_node(
    state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """
    Node to set 'requires_referral_check' flag based on predicted service codes or SOAP content.
    Drives the conditional transition to execute_referral_node.
    """
    updates = {}

    # Check if any predicted code might need referral
    code_based = any(sc.code.startswith("FRACT") for sc in getattr(state, "predicted_service_codes", []))

    # Check if SOAP text matches any referral rule that requires referral
    text_based = False
    from app.core.referral_nodes import REFERRAL_RULES
    soap_lower = state.soap_text.lower()
    for rule in REFERRAL_RULES:
        if rule.get("referral_required", False):
            keywords = rule.get("keywords", [])
            if any(kw.lower() in soap_lower for kw in keywords):
                text_based = True
                break

    requires_referral = code_based or text_based
    updates["requires_referral_check"] = requires_referral

    # Determine what triggered referral
    triggered_by = None
    if text_based:
        triggered_by = "SOAP text"
    elif code_based:
        triggered_by = "Predicted service code"

    # Update reasoning trail
    reasoning_trail = getattr(state, "reasoning_trail", [])
    reasoning_trail.append(f"Check referral required: {requires_referral} (triggered_by={triggered_by})")
    updates["reasoning_trail"] = reasoning_trail

    # Append stage
    stages = getattr(state, "stages", [])
    stages.append(StageEvent(
        code="check_referral_required",
        description="Checked if referral is required",
        data={
            "requires_referral_check": requires_referral,
            "triggered_by": triggered_by,
            "code_based": code_based,
            "text_based": text_based
        }
    ))
    updates["stages"] = stages

    # Send WebSocket update
    if ws_send:
        try:
            await ws_send({
                "event_type": "node_update",
                "node": "check_referral_required",
                "payload": state.model_copy(update=updates).dict()
            })
        except Exception as e:
            logger.error(f"[REFERRAL_NODE] Failed sending ws update: {e}")

    return updates
