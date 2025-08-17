import os
import subprocess
from typing import Dict, Any, Optional, Callable
from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.utils.logging import get_logger
from app.config import USE_GEMINI_FOR_PATIENT_SUMMARY, GEMINI_PATIENT_SUMMARY_API_KEY, LOCAL_LLM_PATH

logger = get_logger(__name__)

# ---------------------------
# Optional Gmail integration
# ---------------------------
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    GMAIL_ENABLED = True
except ImportError:
    logger.warning("[REFERRAL_DRAFT_NODE] Gmail integration not installed. Skipping email draft creation.")
    GMAIL_ENABLED = False

# ---------------------------
# Helper: Run Local LLaMA
# ---------------------------
def run_local_llama(prompt: str, temperature: float = 0.8, threads: int = 8) -> str:
    """
    Runs local LLaMA to generate referral draft text.
    """
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_file_dir, "..", ".."))
    llama_exe_path = os.path.join(project_root, "models", "llama-b6018-bin-win-cpu-x64", "llama-run.exe")

    if not os.path.exists(llama_exe_path):
        logger.error(f"[REFERRAL_DRAFT_NODE] LLaMA binary not found at {llama_exe_path}")
        return ""

    try:
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
        logger.error(f"[REFERRAL_DRAFT_NODE] Local LLaMA failed:\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
        return ""
    except Exception as e:
        logger.error(f"[REFERRAL_DRAFT_NODE] Local LLaMA failed: {e}")
        return ""

# ---------------------------
# Helper: Gmail Draft
# ---------------------------
def create_gmail_draft(user_creds: Credentials, to: str, subject: str, body: str) -> Optional[str]:
    """
    Creates a draft in Gmail. Returns draft ID or None.
    """
    if not GMAIL_ENABLED:
        logger.warning("[REFERRAL_DRAFT_NODE] Gmail not enabled.")
        return None

    try:
        service = build('gmail', 'v1', credentials=user_creds)
        message = {
            'message': {
                'to': to,
                'subject': subject,
                'body': body
            }
        }
        draft = service.users().drafts().create(userId="me", body=message).execute()
        return draft.get("id")
    except Exception as e:
        logger.error(f"[REFERRAL_DRAFT_NODE] Failed to create Gmail draft: {e}")
        return None

# ---------------------------
# Referral Draft Node
# ---------------------------
async def generate_referral_draft_node(
    state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None,
    gmail_creds: Optional[Any] = None  # pass OAuth2 Credentials if Gmail integration is desired
) -> Dict[str, Any]:
    """
    Generates a referral letter if referral is required.
    Optionally creates Gmail draft.
    """
    updates: Dict[str, Any] = {}

    # Check precondition
    if not getattr(state, "referral_required", False):
        reasoning = "Referral not required, skipping draft generation."
        logger.info(f"[REFERRAL_DRAFT_NODE] {reasoning}")
        updates["reasoning_trail"] = getattr(state, "reasoning_trail", []) + [reasoning]
        return updates

    # ---------------------------
    # Prepare prompt for AI
    # ---------------------------
    prompt = f"""
You are a medical assistant AI.
Generate a concise, professional referral letter for a specialist.
Include:

- Patient info: {getattr(state, 'patient_info', 'N/A')}
- Relevant history and SOAP note: {state.soap_text}
- Diagnoses / predicted codes: {', '.join([sc.code for sc in getattr(state, 'predicted_service_codes', [])]) if getattr(state, 'predicted_service_codes', []) else 'None'}
- Reason for referral: {getattr(state, 'referral_rule_applied', 'General referral')}
- Suggested specialist or department: {getattr(state, 'suggested_specialist', 'N/A')}
- Polite closing and signature

Do not make assumptions beyond the provided information.
"""

    # ---------------------------
    # Generate draft using AI
    # ---------------------------
    referral_draft = ""
    try:
        if USE_GEMINI_FOR_PATIENT_SUMMARY and GEMINI_PATIENT_SUMMARY_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_PATIENT_SUMMARY_API_KEY)
            gemini_model = genai.GenerativeModel("gemini-1.5-flash")
            response = gemini_model.generate_content(prompt)
            referral_draft = response.text.strip()
        else:
            referral_draft = run_local_llama(prompt)
    except Exception as e:
        logger.error(f"[REFERRAL_DRAFT_NODE] AI generation failed: {e}")

    if not referral_draft:
        referral_draft = "Referral draft could not be generated by AI."
        logger.warning("[REFERRAL_DRAFT_NODE] Using fallback draft.")

    updates["referral_draft_text"] = referral_draft

    # ---------------------------
    # Optional: Gmail draft
    # ---------------------------
    draft_id = None
    if gmail_creds:
        subject = f"Referral for patient {getattr(state, 'patient_info', 'N/A')}"
        to = getattr(state, "gp_email", "")
        draft_id = create_gmail_draft(gmail_creds, to, subject, referral_draft)
        updates["gmail_draft_id"] = draft_id

    # ---------------------------
    # Reasoning trail & stage
    # ---------------------------
    reasoning_trail = getattr(state, "reasoning_trail", [])
    reasoning_trail.append(f"Generated referral draft. Gmail draft created: {'Yes' if draft_id else 'No'}")
    updates["reasoning_trail"] = reasoning_trail

    stages = getattr(state, "stages", [])
    stages.append(StageEvent(
        code="generate_referral_draft",
        description="Referral draft generated",
        data={
            "referral_draft": referral_draft[:200] + ("..." if len(referral_draft) > 200 else ""),
            "gmail_draft_id": draft_id
        }
    ))
    updates["stages"] = stages

    # ---------------------------
    # WebSocket update
    # ---------------------------
    if ws_send:
        try:
            await ws_send({
                "event_type": "node_update",
                "node": "generate_referral_draft",
                "payload": state.model_copy(update=updates).dict()
            })
        except Exception as e:
            logger.error(f"[REFERRAL_DRAFT_NODE] WS update failed: {e}")

    return updates
