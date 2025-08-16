# import asyncio
# from typing import List, Dict, Any
# from fastapi import WebSocket
# from langgraph.graph import StateGraph, END
# from datetime import datetime
#
# from app.schemas_new.agentic_state import AgenticState
# from app.core.predict_rerank_validate_nodes import (
#     predict_service_codes_node,
#     rerank_service_codes_node,
#     validate_soap_node,
#     question_generation_node,
#     output_node
# )
# import app.core.pii_nodes as pii_nodes
# from app.utils.logging import get_logger
#
# logger = get_logger(__name__)
#
# # ---------------------------------
# # Helper (instead of importing timestamped)
# # ---------------------------------
# def ts(msg: str) -> str:
#     return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
#
# # ----------------------------
# # LangGraph Workflow Definition
# # ----------------------------
# workflow = StateGraph(AgenticState)
#
# workflow.add_node("pii_detection", pii_nodes.pii_detection_node)
# workflow.add_node("anonymize_pii", pii_nodes.anonymize_pii_node)
# workflow.add_node("predict_service_codes", predict_service_codes_node)
# workflow.add_node("rerank_service_codes", rerank_service_codes_node)
# workflow.add_node("validate_soap", validate_soap_node)
# workflow.add_node("question_generation", question_generation_node)
# workflow.add_node("output", output_node)
#
# workflow.set_entry_point("pii_detection")
#
# workflow.add_conditional_edges(
#     "pii_detection",
#     lambda state: "anonymize_pii" if state.pii_present else "predict_service_codes",
#     {
#         "anonymize_pii": "anonymize_pii",
#         "predict_service_codes": "predict_service_codes"
#     }
# )
#
# workflow.add_edge("anonymize_pii", "predict_service_codes")
# workflow.add_edge("predict_service_codes", "rerank_service_codes")
# workflow.add_edge("rerank_service_codes", "validate_soap")
# workflow.add_edge("validate_soap", "question_generation")
# workflow.add_conditional_edges(
#     "question_generation",
#     lambda state: "END" if state.waiting_for_user else "output",
#     {"END": END, "output": "output"}
# )
# workflow.add_edge("output", END)
#
# compiled_workflow = workflow.compile()
#
# # ----------------------------
# #   Runner
# # ----------------------------
# async def run_workflow(
#     initial_state: AgenticState
# ) -> AgenticState:
#     logger.info(ts(f"[ORCHESTRATOR] Starting run_workflow for session_id={initial_state.session_id}"))
#
#     state = initial_state
#     logger.info(ts(f"[WORKFLOW] Starting/Resuming workflow from a clean slate."))
#
#     final_state = None
#     async for step_output in compiled_workflow.astream(state):
#         step_name = list(step_output.keys())[0]
#         logger.info(ts(f"[WORKFLOW] Executing node: {step_name}"))
#
#         updates = step_output[step_name]
#         print(f"[DEBUG NODE RETURN] {step_name} returned => {updates} (type={type(updates)})")
#
#         if updates is not None:
#             state = state.update(**updates)
#             logger.info(ts(f"[WORKFLOW] State after {step_name} update: {state.dict()}"))
#         else:
#             print(f"[DEBUG] {step_name} returned None => skipping update")
#
#         final_state = state
#
#     logger.info(ts("[WORKFLOW] Workflow finished"))
#     return final_state
import asyncio
from typing import List, Dict, Any, Optional, Callable
from fastapi import WebSocket
from langgraph.graph import StateGraph, END
from datetime import datetime

from app.schemas_new.agentic_state import AgenticState
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

# ---------------------------------
# Helper (instead of importing timestamped)
# ---------------------------------
def ts(msg: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

# ----------------------------
# LangGraph Workflow Definition
# ----------------------------
workflow = StateGraph(AgenticState)

workflow.add_node("pii_detection", pii_nodes.pii_detection_node)
workflow.add_node("anonymize_pii", pii_nodes.anonymize_pii_node)
workflow.add_node("predict_service_codes", predict_service_codes_node)
workflow.add_node("rerank_service_codes", rerank_service_codes_node)
workflow.add_node("validate_soap", validate_soap_node)
workflow.add_node("question_generation", question_generation_node)
workflow.add_node("output", output_node)

workflow.set_entry_point("pii_detection")

workflow.add_conditional_edges(
    "pii_detection",
    lambda state: "anonymize_pii" if state.pii_present else "predict_service_codes",
    {
        "anonymize_pii": "anonymize_pii",
        "predict_service_codes": "predict_service_codes"
    }
)

workflow.add_edge("anonymize_pii", "predict_service_codes")
workflow.add_edge("predict_service_codes", "rerank_service_codes")
workflow.add_edge("rerank_service_codes", "validate_soap")
workflow.add_edge("validate_soap", "question_generation")
workflow.add_conditional_edges(
    "question_generation",
    lambda state: "END" if state.waiting_for_user else "output",
    {"END": END, "output": "output"}
)
workflow.add_edge("output", END)

compiled_workflow = workflow.compile()

# ----------------------------
#   Runner with optional WebSocket updates
# ----------------------------
async def run_workflow(
    initial_state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], None]] = None
) -> AgenticState:
    """
    Runs the compiled workflow. Sends reasoning_trail updates to UI via `ws_send` callable if provided.
    """
    logger.info(ts(f"[ORCHESTRATOR] Starting run_workflow for session_id={initial_state.session_id}"))
    state = initial_state
    logger.info(ts(f"[WORKFLOW] Starting/Resuming workflow from a clean slate."))

    final_state = state
    async for step_output in compiled_workflow.astream(state):
        step_name = list(step_output.keys())[0]
        updates = step_output[step_name]
        logger.info(ts(f"[WORKFLOW] Executing node: {step_name}"))

        print(f"[DEBUG NODE RETURN] {step_name} returned => {updates} (type={type(updates)})")

        if updates is None:
            updates = {}

        # Ensure reasoning_trail is always included
        if "reasoning_trail" not in updates:
            updates["reasoning_trail"] = state.reasoning_trail

        try:
            state = state.update(**updates)
            final_state = state
            logger.info(ts(f"[WORKFLOW] State after {step_name} update: {state.dict()}"))
        except Exception as e:
            logger.error(ts(f"[WORKFLOW] Error updating state at node {step_name}: {e}"))

        # Send reasoning_trail / updates to frontend if ws_send provided
        if ws_send:
            try:
                ws_send({
                    "event_type": "node_update",
                    "node": step_name,
                    "payload": updates
                })
            except Exception as e:
                logger.error(ts(f"[WORKFLOW] Failed sending update to UI: {e}"))

    logger.info(ts("[WORKFLOW] Workflow finished"))
    return final_state
