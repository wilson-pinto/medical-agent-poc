import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from langgraph.graph import StateGraph, END

from app.core.referral_nodes import execute_referral_node, check_referral_required_node
from app.core.generate_referral_draft_node import generate_referral_draft_node
from app.core.patient_summary_node import patient_summary_node
from app.core.patient_summary_pdf_node import patient_summary_pdf_node
from app.core.dummy_end_node import dummy_end_node

from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.core.predict_rerank_validate_nodes import (
    predict_service_codes_node,
    rerank_service_codes_node,
    validate_soap_node,
    question_generation_node,
    output_node
)
import app.core.pii_nodes as pii_nodes
from app.utils.logging import get_logger

logger = get_logger(__name__)

def ts(msg: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"


# ---------------------------------
# Build LangGraph Workflow
# ---------------------------------
workflow = StateGraph(AgenticState)

# PII nodes
workflow.add_node("pii_detection", pii_nodes.pii_detection_node)
workflow.add_node("anonymize_pii", pii_nodes.anonymize_pii_node)

# Service code & SOAP validation nodes
workflow.add_node("predict_service_codes", predict_service_codes_node)
workflow.add_node("rerank_service_codes", rerank_service_codes_node)
workflow.add_node("validate_soap", validate_soap_node)

# Referral nodes
workflow.add_node("check_referral_required", check_referral_required_node)
workflow.add_node("execute_referral", execute_referral_node)
workflow.add_node("generate_referral_draft", generate_referral_draft_node)

# Question & output nodes
workflow.add_node("question_generation", question_generation_node)
workflow.add_node("output", output_node)

# Patient summary nodes
workflow.add_node("patient_summary", patient_summary_node)
workflow.add_node("patient_summary_pdf", patient_summary_pdf_node)

# Dummy end node
workflow.add_node("dummy_end", dummy_end_node)

workflow.set_entry_point("pii_detection")

# ---------------------------
# Workflow Edges
# ---------------------------

# PII branching
workflow.add_conditional_edges(
    "pii_detection",
    lambda state: "anonymize_pii" if state.pii_present else "predict_service_codes",
    {"anonymize_pii": "anonymize_pii", "predict_service_codes": "predict_service_codes"}
)
workflow.add_edge("anonymize_pii", "predict_service_codes")

# Service code & SOAP flow
workflow.add_edge("predict_service_codes", "rerank_service_codes")
workflow.add_edge("rerank_service_codes", "validate_soap")
workflow.add_edge("validate_soap", "check_referral_required")

# Referral branching
workflow.add_conditional_edges(
    "check_referral_required",
    lambda state: "execute_referral" if getattr(state, "requires_referral_check", False) else "question_generation",
    {"execute_referral": "execute_referral", "question_generation": "question_generation"}
)
workflow.add_conditional_edges(
    "execute_referral",
    lambda state: "generate_referral_draft" if getattr(state, "referral_required", False) else "question_generation",
    {"generate_referral_draft": "generate_referral_draft", "question_generation": "question_generation"}
)
workflow.add_edge("generate_referral_draft", "question_generation")

# Question / output flow
workflow.add_conditional_edges(
    "question_generation",
    lambda state: "END" if state.waiting_for_user else "output",
    {"output": "output", "END": END}
)

# Patient summary & PDF
workflow.add_edge("output", "patient_summary")
workflow.add_edge("patient_summary", "patient_summary_pdf")

# PDF -> dummy end node
workflow.add_edge("patient_summary_pdf", "dummy_end")

compiled_workflow = workflow.compile()


# ---------------------------------
# Runner
# ---------------------------------
async def run_workflow(
    initial_state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> AgenticState:

    logger.info(ts(f"[ORCHESTRATOR] Starting run_workflow for session {initial_state.session_id}"))
    initial_state.loop_count = getattr(initial_state, "loop_count", 0) + 1

    state = initial_state
    final_state = state

    async for step_output in compiled_workflow.astream(state):
        step_name = next(iter(step_output))
        updates = step_output[step_name] or {}
        logger.info(ts(f"[WORKFLOW] Executing node: {step_name}"))

        updates.setdefault("reasoning_trail", state.reasoning_trail)
        stages = getattr(state, "stages", [])
        stages.append(StageEvent(code=step_name, description=f"Node executed: {step_name}", data=updates))
        updates["stages"] = stages

        try:
            state = state.model_copy(update=updates)
            final_state = state
        except Exception as e:
            logger.error(ts(f"[WORKFLOW] Failed updating state @ {step_name}: {e}"))

        # WS updates
        if ws_send:
            try:
                await ws_send({
                    "event_type": "node_update",
                    "node": step_name,
                    "payload": state.dict()
                })
                await ws_send({
                    "event_type": "stage_update",
                    "stage": step_name
                })

                if getattr(state, "waiting_for_user", False):
                    await ws_send({
                        "event_type": "waiting_for_user",
                        "payload": {
                            "question": getattr(state, "question", ""),
                            "reasoning_trail": state.reasoning_trail,
                            "predicted_service_codes": [c.model_dump() for c in (state.predicted_service_codes or [])]
                        }
                    })
                    break

                # PDF generation guaranteed after patient_summary node
                if step_name == "patient_summary":
                    pdf_updates = await patient_summary_pdf_node(state, ws_send=ws_send)
                    state = state.model_copy(update=pdf_updates)
                    final_state = state
                    pdf_path = pdf_updates.get("patient_summary_pdf_path")
                    if pdf_path:
                        await ws_send({
                            "event_type": "pdf_ready",
                            "payload": {
                                "filename": Path(pdf_path).name,
                                "download_url": f"/api/download_pdf/{state.session_id}"
                            }
                        })

            except Exception as e:
                logger.error(ts(f"[WORKFLOW] Failed sending WS update: {e}"))

    logger.info(ts("[WORKFLOW] Workflow finished"))

    if ws_send and not getattr(state, "waiting_for_user", False):
        try:
            await ws_send({
                "event_type": "workflow_finished",
                "payload": state.dict()
            })
        except Exception as e:
            logger.error(ts(f"[WORKFLOW] Final send failed: {e}"))

    return final_state
