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
# Run workflow with pause and safe loop handling
# ----------------------------

def update_agentic_state(state: AgenticState, step_output: dict):
    """
    Safely update AgenticState using node outputs.
    Only set keys that exist in AgenticState or are valid fields.
    """
    for node_name, node_result in step_output.items():
        if not isinstance(node_result, dict):
            # e.g., simple scalar result
            if hasattr(state, node_name):
                setattr(state, node_name, node_result)
            continue

        # Map nested node outputs to AgenticState attributes
        for key, value in node_result.items():
            if hasattr(state, key):
                setattr(state, key, value)
            else:
                # Optional: log unmapped keys without raising
                print(f"[WARN] Key '{key}' from node '{node_name}' not in AgenticState. Skipping.")
    return state




def run_workflow_with_pause(initial_state: AgenticState) -> AgenticState:
    """
    Runs the workflow step-by-step, pausing if user input is required.
    Handles loop count to prevent infinite loops.
    Automatically flattens node outputs so they update AgenticState correctly.
    """
    state = initial_state
    print("[DEBUG][run_workflow_with_pause] Starting workflow...")

    for step_output in compiled_workflow.stream(state):
        print(f"[DEBUG] step_output: {step_output}")

        # Flatten nested node outputs
        def apply_to_state(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    apply_to_state({k: v})
            else:
                return obj

        state = update_agentic_state(state, step_output)

        # Increment loop counter safely
        state.loop_count = getattr(state, "loop_count", 0) + 1
        print(f"[DEBUG] loop_count: {state.loop_count}")

        # Safety: stop if loop_count exceeds max_loops
        if state.loop_count >= getattr(state, "max_loops", 5):
            print(f"[WARN] Max loops reached ({state.max_loops}). Forcing workflow stop.")
            state.waiting_for_user = False
            break

        # Pause workflow if waiting for user input
        if getattr(state, "waiting_for_user", False):
            print("[DEBUG] Workflow paused. Waiting for user input...")
            print(f"[DEBUG] Question: {getattr(state, 'question', None)}")
            break

    # Workflow completed without pause
    if not getattr(state, "waiting_for_user", False):
        print("[DEBUG] Workflow completed.")
        print(f"[DEBUG] Final predicted_service_codes: {[sc.code for sc in state.predicted_service_codes]}")

    return state

