# app/core/patient_summary_node.py
from typing import Dict, Any, Optional, Callable
from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)

async def patient_summary_node(
    state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> Dict[str, Any]:
    """
    Generates a patient-friendly summary from SOAP note, predicted codes, and referrals.
    """
    updates: Dict[str, Any] = {}

    # Compose summary
    summary_lines = []
    summary_lines.append("Dear patient, here is a summary of your recent consultation:")

    # Brief SOAP overview
    summary_lines.append(
        f"- Condition noted: {state.soap_text[:150]}{'...' if len(state.soap_text) > 150 else ''}"
    )

    # Include predicted codes
    if state.predicted_service_codes:
        codes_list = ", ".join([sc.code for sc in state.predicted_service_codes])
        summary_lines.append(f"- Related service codes: {codes_list}")

    # Include referral info if applicable
    if getattr(state, "referral_required", False):
        summary_lines.append(f"- Referral required: {state.referral_rule_applied}")
    else:
        summary_lines.append("- No referral required at this time.")

    # Combine into one summary
    patient_summary = "\n".join(summary_lines)
    updates["patient_summary"] = patient_summary

    # Update reasoning trail
    reasoning_trail = getattr(state, "reasoning_trail", [])
    reasoning_trail.append("Generated patient-friendly summary.")
    updates["reasoning_trail"] = reasoning_trail

    # Append stage
    stages = getattr(state, "stages", [])
    stages.append(StageEvent(
        code="patient_summary",
        description="Patient-friendly summary generated",
        data={"patient_summary": patient_summary}
    ))
    updates["stages"] = stages

    # Send WebSocket update if available
    if ws_send:
        try:
            await ws_send({
                "event_type": "node_update",
                "node": "patient_summary",
                "payload": state.model_copy(update=updates).dict()
            })
        except Exception as e:
            logger.error(f"[PATIENT_SUMMARY_NODE] Failed sending ws update: {e}")

    return updates
