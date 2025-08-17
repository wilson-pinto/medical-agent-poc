# app/core/patient_summary_node.py
import os
import subprocess
from typing import Dict, Any, Optional, Callable
from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.utils.logging import get_logger
from app.config import USE_GEMINI_FOR_PATIENT_SUMMARY, GEMINI_PATIENT_SUMMARY_API_KEY, LOCAL_LLM_PATH

logger = get_logger(__name__)

# ---------------------------
# Gemini LLM setup
# ---------------------------
import google.generativeai as genai

# The global configuration has been removed from here.
# The API key will now be configured just before the call is made.
# The 'gemini_model' variable is no longer needed at the global scope.

# ---------------------------
# Local LLM setup (using precompiled LLaMA binary)
# ---------------------------
def run_local_llama(prompt: str, temperature: float = 0.8, threads: int = 8) -> str:
    """
    Runs the local LLaMA model binary and returns the output text.
    Uses llama-run.exe on Windows.
    """
    # Find the project root by navigating up from the current file's location
    current_file_dir = os.path.dirname(os.path.abspath(__file__))

    # Go up two directories from the current file's directory to reach the project root.
    project_root = os.path.abspath(os.path.join(current_file_dir, "..", ".."))

    logger.info(f"[PATIENT_SUMMARY_NODE] Current file directory: {current_file_dir}")
    logger.info(f"[PATIENT_SUMMARY_NODE] Calculated project root: {project_root}")

    # Build the full path to the executable
    llama_exe_path = os.path.join(project_root, "models", "llama-b6018-bin-win-cpu-x64", "llama-run.exe")

    logger.info(f"[PATIENT_SUMMARY_NODE] Constructed executable path: {llama_exe_path}")

    if not os.path.exists(llama_exe_path):
        logger.error(f"[PATIENT_SUMMARY_NODE] LLaMA binary not found at {llama_exe_path}")
        return ""

    try:
        # Correct command line arguments for llama-run.exe
        result = subprocess.run(
            [
                llama_exe_path,
                LOCAL_LLM_PATH,
                "--temp", str(temperature),
                "-t", str(threads),
                "--prompt", prompt
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"[PATIENT_SUMMARY_NODE] Local LLaMA failed:\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
        return ""
    except Exception as e:
        logger.error(f"[PATIENT_SUMMARY_NODE] Local LLaMA failed: {e}")
        return ""

# ---------------------------
# Patient summary node
# ---------------------------
async def patient_summary_node(
    state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> Dict[str, Any]:
    """
    Generates a patient-friendly summary from SOAP note, predicted codes, and referrals.
    Uses Gemini or local LLM if available, else falls back to template summary.
    """
    updates: Dict[str, Any] = {}
    patient_summary = ""

    # ---------------------------
    # Prepare prompt
    # ---------------------------
    prompt = f"""
You are a medical assistant.
Write a concise, patient-friendly summary based on the following consultation details:

SOAP note: "{state.soap_text}"

Predicted service codes: {', '.join([sc.code for sc in state.predicted_service_codes]) if state.predicted_service_codes else 'None'}

Referral required: {getattr(state, 'referral_required', False)}

Write the summary as a polite letter to the patient.
"""

    # ---------------------------
    # Attempt LLM-based summary
    # ---------------------------
    try:
        if USE_GEMINI_FOR_PATIENT_SUMMARY and GEMINI_PATIENT_SUMMARY_API_KEY:
            # Configure the API key right before making the API call.
            # This ensures that even if another part of the code overwrites the key,
            # this specific call will use the correct one.
            genai.configure(api_key=GEMINI_PATIENT_SUMMARY_API_KEY)

            # Initialize the model right before use.
            gemini_model = genai.GenerativeModel("gemini-1.5-flash")

            response = gemini_model.generate_content(prompt)
            patient_summary = response.text.strip()
            logger.info("[PATIENT_SUMMARY_NODE] Gemini LLM generated summary.")
        else:
            logger.info(f"[PATIENT_SUMMARY_NODE] Using model: {LOCAL_LLM_PATH}")
            patient_summary = run_local_llama(prompt)
            if patient_summary:
                logger.info("[PATIENT_SUMMARY_NODE] Local LLaMA generated summary.")
    except Exception as e:
        logger.error(f"[PATIENT_SUMMARY_NODE] LLM generation failed: {e}")

    # ---------------------------
    # Fallback template summary
    # ---------------------------
    if not patient_summary:
        summary_lines = ["Dear patient, here is a summary of your recent consultation:"]
        summary_lines.append(f"- Condition noted: {state.soap_text[:150]}{'...' if len(state.soap_text) > 150 else ''}")

        if state.predicted_service_codes:
            codes_list = ", ".join([sc.code for sc in state.predicted_service_codes])
            summary_lines.append(f"- Related service codes: {codes_list}")

        if getattr(state, "referral_required", False):
            summary_lines.append(f"- Referral required: {state.referral_rule_applied}")
        else:
            summary_lines.append("- No referral required at this time.")

        patient_summary = "\n".join(summary_lines)
        logger.info("[PATIENT_SUMMARY_NODE] Fallback summary used.")

    updates["patient_summary"] = patient_summary

    # ---------------------------
    # Reasoning trail
    # ---------------------------
    reasoning_trail = getattr(state, "reasoning_trail", [])
    reasoning_trail.append("Generated patient summary.")
    updates["reasoning_trail"] = reasoning_trail

    # ---------------------------
    # StageEvent
    # ---------------------------
    summary_text = f"Summary created ({len(patient_summary.split())} words)"
    stages = getattr(state, "stages", [])
    stages.append(StageEvent(
        code="patient_summary",
        description="Patient summary created",
        data={"patient_summary": patient_summary, "summary": summary_text}
    ))
    updates["stages"] = stages

    # ---------------------------
    # WebSocket update
    # ---------------------------
    if ws_send:
        try:
            await ws_send({
                "event_type": "node_update",
                "node": "patient_summary",
                "payload": state.model_copy(update=updates).dict()
            })
        except Exception as e:
            logger.error(f"[PATIENT_SUMMARY_NODE] WS failed: {e}")

    return updates
