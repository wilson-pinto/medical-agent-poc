import asyncio
from typing import Optional, Callable
from app.schemas_new.agentic_state import AgenticState
from langgraph.graph import StateGraph, END
from app.core.predict_rerank_validate_nodes import (
    predict_service_codes_node,
    rerank_service_codes_node,
    validate_soap_node,
    question_generation_node,
    user_response_node,
    output_node,
    should_continue
)

# ----------------------------
# Workflow setup
# ----------------------------
workflow = StateGraph(AgenticState)

# Add nodes
workflow.add_node("predict_service_codes", predict_service_codes_node)
workflow.add_node("rerank_service_codes", rerank_service_codes_node)
workflow.add_node("validate_soap", validate_soap_node)
workflow.add_node("question_generation", question_generation_node)
workflow.add_node("user_response", user_response_node)
workflow.add_node("output", output_node)

# Entry point
workflow.set_entry_point("predict_service_codes")

# Edges
workflow.add_edge("predict_service_codes", "rerank_service_codes")
workflow.add_edge("rerank_service_codes", "validate_soap")
workflow.add_edge("validate_soap", "question_generation")
workflow.add_conditional_edges(
    "question_generation",
    should_continue,
    {"user_response": "user_response", "output": "output"}
)
workflow.add_edge("user_response", "question_generation")
workflow.add_edge("output", END)

# Compile workflow
compiled_workflow = workflow.compile()


# ----------------------------
# Update AgenticState safely
# ----------------------------
def update_agentic_state(state: AgenticState, step_output: dict) -> AgenticState:
    for node_name, node_result in step_output.items():
        if not isinstance(node_result, dict):
            if hasattr(state, node_name):
                setattr(state, node_name, node_result)
            continue

        for key, value in node_result.items():
            if hasattr(state, key):
                setattr(state, key, value)
            else:
                print(f"[WARN] Key '{key}' from node '{node_name}' not in AgenticState. Skipping.")
    return state


# ----------------------------
# Run workflow with pause, safe loops, and live events
# ----------------------------
# ----------------------------
# Run workflow with pause, safe loops, and live events
# ----------------------------
def run_workflow_with_pause(
    initial_state: AgenticState,
    event_callback: Optional[Callable[[str, dict], None]] = None,
    session_id: Optional[str] = None
) -> AgenticState:
    import asyncio

    state = initial_state
    print("[DEBUG][run_workflow_with_pause] Starting workflow...")

    for step_output in compiled_workflow.stream(state):
        print(f"[DEBUG] step_output: {step_output}")

        # Update AgenticState
        state = update_agentic_state(state, step_output)

        # Increment loop count
        state.loop_count = getattr(state, "loop_count", 0) + 1
        print(f"[DEBUG] loop_count: {state.loop_count}")

        # Send live event for this workflow step
        if event_callback:
            asyncio.create_task(event_callback("workflow_step", {
                "session_id": session_id,
                "step_output": step_output,
                "predicted_service_codes": [sc.dict() for sc in state.predicted_service_codes],
                "question": getattr(state, "question", None),
                "waiting_for_user": getattr(state, "waiting_for_user", False),
                "reasoning_trail": state.reasoning_trail,
                "loop_count": state.loop_count
            }))

        # Safety: stop if loop_count exceeds max_loops
        if state.loop_count >= getattr(state, "max_loops", 5):
            print(f"[WARN] Max loops reached ({state.max_loops}). Stopping workflow.")
            state.waiting_for_user = False
            break

        # Pause workflow if waiting for user input
        if getattr(state, "waiting_for_user", False):
            print("[DEBUG] Workflow paused. Waiting for user input...")
            if event_callback:
                # Try to get service_code from step_output or state
                service_code = None
                if step_output.get("question_generation"):
                    service_code = step_output["question_generation"].get("service_code")
                if not service_code:
                    service_code = getattr(state, "current_service_code", None)

                asyncio.create_task(event_callback("waiting_for_user", {
                    "session_id": session_id,
                    "question": state.question,
                    "service_code": service_code or "demo_code"  # ✅ always send something
                }))
            break


    # Workflow completed
    if not getattr(state, "waiting_for_user", False):
        print("[DEBUG] Workflow completed.")
        print(f"[DEBUG] Final predicted_service_codes: {[sc.code for sc in state.predicted_service_codes]}")
        if event_callback:
            asyncio.create_task(event_callback("workflow_completed", {
                "session_id": session_id,
                "predicted_service_codes": [sc.dict() for sc in state.predicted_service_codes]
            }))

    return state

