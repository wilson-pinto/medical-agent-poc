# import asyncio
# from typing import Optional, Callable
# from datetime import datetime
# from langgraph.graph import StateGraph, END
# from app.schemas_new.agentic_state import AgenticState
# from app.core.predict_rerank_validate_nodes import (
#     predict_service_codes_node,
#     rerank_service_codes_node,
#     validate_soap_node,
#     question_generation_node,
#     user_response_node,
#     output_node,
#     should_continue
# )
#
# # ----------------------------
# # Workflow setup
# # ----------------------------
# workflow = StateGraph(AgenticState)
#
# # Add nodes
# workflow.add_node("predict_service_codes", predict_service_codes_node)
# workflow.add_node("rerank_service_codes", rerank_service_codes_node)
# workflow.add_node("validate_soap", validate_soap_node)
# workflow.add_node("question_generation", question_generation_node)
# workflow.add_node("user_response", user_response_node)
# workflow.add_node("output", output_node)
#
# # Entry point
# workflow.set_entry_point("predict_service_codes")
#
# # Edges
# workflow.add_edge("predict_service_codes", "rerank_service_codes")
# workflow.add_edge("rerank_service_codes", "validate_soap")
# workflow.add_edge("validate_soap", "question_generation")
# workflow.add_conditional_edges(
#     "question_generation",
#     should_continue,
#     {"user_response": "user_response", "output": "output"}
# )
# workflow.add_edge("user_response", "question_generation")
# workflow.add_edge("output", END)
#
# # Compile workflow
# compiled_workflow = workflow.compile()
#
# # ----------------------------
# # Utility functions
# # ----------------------------
# def timestamped(msg: str) -> str:
#     return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
#
# def update_agentic_state(state: AgenticState, step_output: dict) -> AgenticState:
#     """
#     Safely update AgenticState with step_output from workflow.
#     This function has been fixed to correctly map the data from each node's output
#     to the corresponding fields in the AgenticState object.
#     """
#     if not step_output or not isinstance(step_output, dict):
#         return state
#
#     for key, value in step_output.items():
#         if key == "predict_service_codes":
#             # FIX: Extract the specific 'predicted_service_codes' list from the output
#             # and append the reasoning trail.
#             state.predicted_service_codes = value.get('predicted_service_codes', [])
#             state.candidates = value.get('candidates', [])
#             state.reasoning_trail.extend(value.get('reasoning_trail', []))
#
#         elif key == "rerank_service_codes":
#             # FIX: Extract 'reranked_code' and update the predicted_service_codes list.
#             state.reranked_code = value.get('reranked_code', None)
#             if state.predicted_service_codes:
#                 # Update the first item in the list with the validated version
#                 state.predicted_service_codes[0] = value.get('predicted_service_codes', state.predicted_service_codes)[0]
#             state.reasoning_trail.extend(value.get('reasoning_trail', []))
#
#         elif key == "validate_soap":
#             # FIX: Update the predicted_service_codes list with the validated info.
#             if state.predicted_service_codes:
#                 state.predicted_service_codes = value.get('predicted_service_codes', state.predicted_service_codes)
#             state.reasoning_trail.extend(value.get('reasoning_trail', []))
#
#         elif key == "question_generation":
#             # FIX: Correctly extract the question text and update waiting_for_user status.
#             question_data = value.get('question')
#             state.question = question_data
#             state.waiting_for_user = bool(question_data)
#             state.reasoning_trail.extend(value.get('reasoning_trail', []))
#
#         elif key == "user_response":
#             # FIX: Correctly update user_responses from the output.
#             state.user_responses.update(value.get('responses', {}))
#
#         elif key == "output":
#             # The output node typically generates the final output, not a state update.
#             pass
#         else:
#             state.reasoning_trail.append(timestamped(f"[update_agentic_state] Unknown key: {key}"))
#
#     return state
#
# def run_workflow_with_pause(
#     initial_state: AgenticState,
#     event_callback: Optional[Callable[[str, AgenticState], None]] = None,
#     session_id: Optional[str] = None
# ) -> AgenticState:
#     """
#     Runs the compiled workflow with detailed logging and optional event callback.
#     This function has been streamlined and now relies on the corrected update_agentic_state.
#     """
#     state = initial_state
#     print(timestamped(f"[DEBUG] Starting workflow for session_id={session_id}"))
#     print(timestamped(f"[DEBUG] Initial state type: {type(state)}, state: {state}"))
#
#     try:
#         for step_output in compiled_workflow.stream(state):
#             print(timestamped(f"\n[DEBUG][STEP OUTPUT] Raw output: {step_output}"))
#             print(timestamped(f"[DEBUG] State BEFORE update: {state.__dict__}"))
#
#             # Safely and correctly update AgenticState
#             state = update_agentic_state(state, step_output)
#             print(timestamped(f"[DEBUG] State AFTER update: {state.__dict__}"))
#
#             # Increment loop counter
#             state.loop_count += 1
#             print(timestamped(f"[DEBUG] loop_count incremented to {state.loop_count}"))
#
#             # Log critical attributes for debugging
#             print(timestamped(f"[DEBUG] waiting_for_user: {state.waiting_for_user}"))
#             print(timestamped(f"[DEBUG] question: {state.question}"))
#             print(timestamped(f"[DEBUG] predicted_service_codes: {state.predicted_service_codes}"))
#
#             # Event callback
#             if event_callback:
#                 try:
#                     asyncio.create_task(event_callback("workflow_step", state))
#                 except Exception as e:
#                     print(f"[ERROR] Event callback failed: {e}")
#
#             # Stop if max loops reached
#             if state.loop_count >= state.max_loops:
#                 print(timestamped(f"[WARN] Max loops reached ({state.loop_count})"))
#                 state.waiting_for_user = False
#                 break
#
#             # Pause if waiting for user input
#             if state.waiting_for_user:
#                 print(timestamped("[DEBUG] Workflow paused, waiting for user input"))
#                 if event_callback:
#                     try:
#                         asyncio.create_task(event_callback("waiting_for_user", state))
#                     except Exception as e:
#                         print(f"[ERROR] Event callback failed: {e}")
#                 break
#
#         print(timestamped("[DEBUG] Workflow finished"))
#         print(timestamped(f"[DEBUG] Final state: {state.__dict__}"))
#
#     except Exception as e:
#         print(timestamped(f"[ERROR] Exception during workflow: {e}"))
#         print(timestamped(f"[ERROR] Current state dump: {state.__dict__}"))
#         raise
#
#     return state
#
# import asyncio
# from typing import Optional, Callable
# from datetime import datetime
# from langgraph.graph import StateGraph, END
# from app.schemas_new.agentic_state import AgenticState
# from app.core.predict_rerank_validate_nodes import (
#     predict_service_codes_node,
#     rerank_service_codes_node,
#     validate_soap_node,
#     question_generation_node,
#     user_response_node,
#     output_node,
#     should_continue
# )
#
# # ----------------------------
# # Workflow setup
# # ----------------------------
# workflow = StateGraph(AgenticState)
#
# # Add nodes
# workflow.add_node("predict_service_codes", predict_service_codes_node)
# workflow.add_node("rerank_service_codes", rerank_service_codes_node)
# workflow.add_node("validate_soap", validate_soap_node)
# workflow.add_node("question_generation", question_generation_node)
# workflow.add_node("user_response", user_response_node)
# workflow.add_node("output", output_node)
#
# # Entry point
# workflow.set_entry_point("predict_service_codes")
#
# # Edges
# workflow.add_edge("predict_service_codes", "rerank_service_codes")
# workflow.add_edge("rerank_service_codes", "validate_soap")
# workflow.add_edge("validate_soap", "question_generation")
# workflow.add_conditional_edges(
#     "question_generation",
#     should_continue,
#     {"user_response": "user_response", "output": "output"}
# )
# workflow.add_edge("user_response", "question_generation")
# workflow.add_edge("output", END)
#
# # Compile workflow
# compiled_workflow = workflow.compile()
#
# # ----------------------------
# # Utility functions
# # ----------------------------
# def timestamped(msg: str) -> str:
#     return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
#
# def update_agentic_state(state: AgenticState, step_output: dict) -> AgenticState:
#     """
#     Safely update AgenticState with step_output from workflow.
#     This function is now fixed to prevent the duplication of the reasoning trail
#     and correctly maps all data from the step output to the state object.
#     """
#     if not step_output or not isinstance(step_output, dict):
#         return state
#
#     # FIX 1: Update the reasoning trail first, as it's the cumulative log.
#     # The output of each step contains the entire trail, so we replace it.
#     new_reasoning_trail = None
#     for key, value in step_output.items():
#         if 'reasoning_trail' in value:
#             new_reasoning_trail = value['reasoning_trail']
#             break
#     if new_reasoning_trail is not None:
#         state.reasoning_trail = new_reasoning_trail
#
#     # FIX 2: Update other state attributes based on the node's output.
#     for key, value in step_output.items():
#         if key == "predict_service_codes":
#             state.predicted_service_codes = value.get('predicted_service_codes', [])
#             state.candidates = value.get('candidates', [])
#         elif key == "rerank_service_codes":
#             state.reranked_code = value.get('reranked_code', None)
#             if state.predicted_service_codes:
#                 state.predicted_service_codes = value.get('predicted_service_codes', state.predicted_service_codes)
#         elif key == "validate_soap":
#             if state.predicted_service_codes:
#                 state.predicted_service_codes = value.get('predicted_service_codes', state.predicted_service_codes)
#         elif key == "question_generation":
#             state.question = value.get('question')
#             state.waiting_for_user = value.get('waiting_for_user', False)
#         elif key == "user_response":
#             state.user_responses.update(value.get('responses', {}))
#         elif key == "output":
#             # The output node typically generates the final output, not a state update.
#             pass
#
#     return state
#
# # NOTE: The fix is here. You must add `async` to the function definition.
# async def run_workflow_with_pause(
#     initial_state: AgenticState,
#     event_callback: Optional[Callable[[str, AgenticState], None]] = None,
#     session_id: Optional[str] = None
# ) -> AgenticState:
#     """
#     Runs the compiled workflow with detailed logging and optional event callback.
#     This function has been streamlined and now relies on the corrected update_agentic_state.
#     """
#     state = initial_state
#     print(timestamped(f"[DEBUG] Starting workflow for session_id={session_id}"))
#     print(timestamped(f"[DEBUG] Initial state type: {type(state)}, state: {state}"))
#
#     try:
#         # Additional log to indicate the workflow loop is starting/resuming.
#         print(timestamped("[DEBUG] Resuming workflow stream..."))
#         for step_output in compiled_workflow.stream(state):
#             print(timestamped(f"\n[DEBUG][STEP OUTPUT] Raw output: {step_output}"))
#             print(timestamped(f"[DEBUG] State BEFORE update: {state.__dict__}"))
#
#             # Safely and correctly update AgenticState
#             old_reasoning_trail_len = len(state.reasoning_trail)
#             state = update_agentic_state(state, step_output)
#             print(timestamped(f"[DEBUG] State AFTER update: {state.__dict__}"))
#
#             # Log the change in reasoning trail length to confirm the fix is working.
#             new_reasoning_trail_len = len(state.reasoning_trail)
#             print(timestamped(f"[DEBUG] Reasoning trail length changed from {old_reasoning_trail_len} to {new_reasoning_trail_len}"))
#
#             # Increment loop counter
#             state.loop_count += 1
#             print(timestamped(f"[DEBUG] loop_count incremented to {state.loop_count}"))
#
#             # Log critical attributes for debugging
#             print(timestamped(f"[DEBUG] waiting_for_user: {state.waiting_for_user}"))
#             print(timestamped(f"[DEBUG] question: {state.question}"))
#             print(timestamped(f"[DEBUG] predicted_service_codes: {state.predicted_service_codes}"))
#
#             # Event callback
#             if event_callback:
#                 try:
#                     # `event_callback` itself is an async function, so we must schedule it.
#                     asyncio.create_task(event_callback("workflow_step", state))
#                 except Exception as e:
#                     print(f"[ERROR] Event callback failed: {e}")
#
#             # Stop if max loops reached
#             if state.loop_count >= state.max_loops:
#                 print(timestamped(f"[WARN] Max loops reached ({state.loop_count})"))
#                 state.waiting_for_user = False
#                 break
#
#             # Pause if waiting for user input
#             if state.waiting_for_user:
#                 print(timestamped("--- Workflow paused, waiting for user input ---"))
#                 if event_callback:
#                     try:
#                         # `event_callback` itself is an async function, so we must schedule it.
#                         asyncio.create_task(event_callback("waiting_for_user", state))
#                     except Exception as e:
#                         print(f"[ERROR] Event callback failed: {e}")
#                 break
#
#         print(timestamped("[DEBUG] Workflow finished"))
#         print(timestamped(f"[DEBUG] Final state: {state.__dict__}"))
#
#     except Exception as e:
#         print(timestamped(f"[ERROR] Exception during workflow: {e}"))
#         print(timestamped(f"[ERROR] Current state dump: {state.__dict__}"))
#         raise
#
#     return state

# import asyncio
# from typing import Optional, Callable
# from datetime import datetime
# from langgraph.graph import StateGraph, END
# from app.schemas_new.agentic_state import AgenticState
# from app.core.predict_rerank_validate_nodes import (
#     predict_service_codes_node,
#     rerank_service_codes_node,
#     validate_soap_node,
#     question_generation_node,
#     user_response_node,
#     output_node,
#     should_continue
# )
#
# # ----------------------------
# # Workflow setup
# # ----------------------------
# workflow = StateGraph(AgenticState)
#
# # Add nodes
# workflow.add_node("predict_service_codes", predict_service_codes_node)
# workflow.add_node("rerank_service_codes", rerank_service_codes_node)
# workflow.add_node("validate_soap", validate_soap_node)
# workflow.add_node("question_generation", question_generation_node)
# workflow.add_node("user_response", user_response_node)
# workflow.add_node("output", output_node)
#
# # Entry point
# workflow.set_entry_point("predict_service_codes")
#
# # Edges
# workflow.add_edge("predict_service_codes", "rerank_service_codes")
# workflow.add_edge("rerank_service_codes", "validate_soap")
# workflow.add_edge("validate_soap", "question_generation")
# workflow.add_conditional_edges(
#     "question_generation",
#     should_continue,
#     {"user_response": "user_response", "output": "output"}
# )
# # Corrected edge, as previously discussed.
# workflow.add_edge("user_response", "validate_soap")
# workflow.add_edge("output", END)
#
# # Compile workflow
# compiled_workflow = workflow.compile()
#
# # ----------------------------
# # Utility functions
# # ----------------------------
# def timestamped(msg: str) -> str:
#     return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
#
# def update_agentic_state(state: AgenticState, step_output: dict) -> AgenticState:
#     """
#     Safely update AgenticState with step_output from workflow.
#     This function has been completely rewritten to correctly parse and apply
#     the updates from each node's output to the state object.
#     """
#     if not step_output or not isinstance(step_output, dict):
#         return state
#
#     for key, value in step_output.items():
#         if key == "predict_service_codes":
#             state.predicted_service_codes = value.get('predicted_service_codes', [])
#             state.candidates = value.get('candidates', [])
#             state.reasoning_trail = value.get('reasoning_trail', [])
#         elif key == "rerank_service_codes":
#             state.reranked_code = value.get('reranked_code', None)
#             state.reasoning_trail = value.get('reasoning_trail', [])
#         elif key == "validate_soap":
#             state.predicted_service_codes = value.get('predicted_service_codes', state.predicted_service_codes)
#             state.reasoning_trail = value.get('reasoning_trail', [])
#         elif key == "question_generation":
#             state.question = value.get('question')
#             state.waiting_for_user = value.get('waiting_for_user', False)
#             state.reasoning_trail = value.get('reasoning_trail', [])
#         elif key == "user_response":
#             # Correctly handle user_response format which is a list.
#             responses_list = value.get('responses', [])
#             for response_item in responses_list:
#                 service_code = response_item.get('service_code')
#                 answers = response_item.get('answers', {})
#                 if service_code:
#                     state.user_responses[service_code] = answers
#         # No state update from the output node itself.
#
#     return state
#
# # NOTE: The fix is here. You must add `async` to the function definition.
# async def run_workflow_with_pause(
#     initial_state: AgenticState,
#     event_callback: Optional[Callable[[str, AgenticState], None]] = None,
#     session_id: Optional[str] = None
# ) -> AgenticState:
#     """
#     Runs the compiled workflow with detailed logging and optional event callback.
#     This function has been streamlined and now relies on the corrected update_agentic_state.
#     """
#     state = initial_state
#     print(timestamped(f"[DEBUG] Starting workflow for session_id={session_id}"))
#     print(timestamped(f"[DEBUG] Initial state type: {type(state)}, state: {state}"))
#
#     try:
#         # Additional log to indicate the workflow loop is starting/resuming.
#         print(timestamped("[DEBUG] Resuming workflow stream..."))
#         for step_output in compiled_workflow.stream(state):
#             print(timestamped(f"\n[DEBUG][STEP OUTPUT] Raw output: {step_output}"))
#             print(timestamped(f"[DEBUG] State BEFORE update: {state.__dict__}"))
#
#             # Safely and correctly update AgenticState
#             old_reasoning_trail_len = len(state.reasoning_trail)
#             state = update_agentic_state(state, step_output)
#             print(timestamped(f"[DEBUG] State AFTER update: {state.__dict__}"))
#
#             # Log the change in reasoning trail length to confirm the fix is working.
#             new_reasoning_trail_len = len(state.reasoning_trail)
#             print(timestamped(f"[DEBUG] Reasoning trail length changed from {old_reasoning_trail_len} to {new_reasoning_trail_len}"))
#
#             # Increment loop counter
#             state.loop_count += 1
#             print(timestamped(f"[DEBUG] loop_count incremented to {state.loop_count}"))
#
#             # Log critical attributes for debugging
#             print(timestamped(f"[DEBUG] waiting_for_user: {state.waiting_for_user}"))
#             print(timestamped(f"[DEBUG] question: {state.question}"))
#             print(timestamped(f"[DEBUG] predicted_service_codes: {state.predicted_service_codes}"))
#
#             # Event callback
#             if event_callback:
#                 try:
#                     # `event_callback` itself is an async function, so we must schedule it.
#                     asyncio.create_task(event_callback("workflow_step", state))
#                 except Exception as e:
#                     print(f"[ERROR] Event callback failed: {e}")
#
#             # Stop if max loops reached
#             if state.loop_count >= state.max_loops:
#                 print(timestamped(f"[WARN] Max loops reached ({state.loop_count})"))
#                 state.waiting_for_user = False
#                 break
#
#             # Pause if waiting for user input
#             if state.waiting_for_user:
#                 print(timestamped("--- Workflow paused, waiting for user input ---"))
#                 if event_callback:
#                     try:
#                         # `event_callback` itself is an async function, so we must schedule it.
#                         asyncio.create_task(event_callback("waiting_for_user", state))
#                     except Exception as e:
#                         print(f"[ERROR] Event callback failed: {e}")
#                 break
#
#         print(timestamped("[DEBUG] Workflow finished"))
#         print(timestamped(f"[DEBUG] Final state: {state.__dict__}"))
#
#     except Exception as e:
#         print(timestamped(f"[ERROR] Exception during workflow: {e}"))
#         print(timestamped(f"[ERROR] Current state dump: {state.__dict__}"))
#         raise
#
#     return state
#

#agentic_workflow.py
# agentic_workflow.py
# app/core/agentic_workflow.py
# app/core/agentic_workflow.py
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket
from langgraph.graph import StateGraph, END
from app.core.agentic_orchestrator import AgenticOrchestrator
from app.schemas_new.agentic_state import AgenticState
from app.core.predict_rerank_validate_nodes import (
    timestamped,
    predict_service_codes_node,
    rerank_service_codes_node,
    validate_soap_node,
    question_generation_node,
    output_node
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

orchestrator = AgenticOrchestrator()

# ----------------------------
# LangGraph Workflow Definition
# ----------------------------
workflow = StateGraph(AgenticState)
workflow.add_node("predict_service_codes", predict_service_codes_node)
workflow.add_node("rerank_service_codes", rerank_service_codes_node)
workflow.add_node("validate_soap", validate_soap_node)
workflow.add_node("question_generation", question_generation_node)
workflow.add_node("output", output_node)

workflow.set_entry_point("predict_service_codes")
workflow.add_edge("predict_service_codes", "rerank_service_codes")
workflow.add_edge("rerank_service_codes", "validate_soap")

# The validate_soap node should always flow to question_generation.
# The conditional logic is now handled after question_generation runs.
workflow.add_edge("validate_soap", "question_generation")
workflow.add_conditional_edges(
    "question_generation",
    lambda state: "END" if state.waiting_for_user else "output",
    {"END": END, "output": "output"}
)

workflow.add_edge("output", END)
compiled_workflow = workflow.compile()


# ----------------------------
# The core run_workflow function
# ----------------------------
async def run_workflow(
    initial_state: AgenticState,
    websocket: WebSocket,
    user_responses: Dict[str, Any] = None
) -> AgenticState:
    """
    Runs the compiled workflow and streams results back to the client via a WebSocket.
    """
    logger.info(timestamped(f"[ORCHESTRATOR] Starting run_workflow for session_id={initial_state.session_id}"))

    if user_responses:
        logger.info(timestamped("[ORCHESTRATOR] User responses received. Processing and merging into state."))
        initial_state = orchestrator.process_user_input(initial_state, user_responses)
        logger.info(timestamped(f"[ORCHESTRATOR] State after user input merge: {initial_state.dict()}"))

    state = initial_state
    logger.info(timestamped(f"[WORKFLOW] Starting/Resuming workflow from a clean slate."))

    # The stream will run until it reaches a node that returns END
    final_state = None
    async for step_output in compiled_workflow.astream(state):
        step_name = list(step_output.keys())[0]
        logger.info(timestamped(f"[WORKFLOW] Executing node: {step_name}"))

        # Log the state *before* the update
        logger.info(timestamped(f"[WORKFLOW] State before {step_name} update: {state.dict()}"))

        state = state.update(**step_output[step_name])

        # Log the state *after* the update
        logger.info(timestamped(f"[WORKFLOW] State after {step_name} update: {state.dict()}"))

        # The final state of the graph is the last yielded step
        final_state = state

    logger.info(timestamped("[WORKFLOW] Workflow finished"))

    # Now, check the final state of the workflow
    if final_state.waiting_for_user:
        logger.info(timestamped("[ORCHESTRATOR] Workflow ended with 'waiting_for_user' flag set to True. Sending prompt to client."))
        await websocket.send_json({"event_type": "waiting_for_user", "payload": final_state.dict()})
    else:
        logger.info(timestamped("[ORCHESTRATOR] Workflow ended with 'waiting_for_user' flag set to False. Sending final document to client."))
        await websocket.send_json({"event_type": "final_document", "payload": final_state.dict()})

    return final_state
