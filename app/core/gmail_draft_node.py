# app/core/gmail_draft_node.py

import base64
from email.mime.text import MIMEText
from typing import Callable, Optional, Dict, Any
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.compose']

# ----------------------------
# Authenticate Gmail
# ----------------------------
def get_gmail_service():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('gmail', 'v1', credentials=creds)
    return service

# ----------------------------
# Create Draft
# ----------------------------
def create_gmail_draft(service, to: str, subject: str, body_text: str):
    message = MIMEText(body_text)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft_body = {'message': {'raw': raw}}
    draft = service.users().drafts().create(userId='me', body=draft_body).execute()
    logger.info(f"[GMAIL_DRAFT_NODE] Draft created with ID: {draft['id']}")
    return draft

# ----------------------------
# Execute Node
# ----------------------------
async def execute_gmail_draft_node(
    state: AgenticState,
    ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> Dict[str, Any]:

    updates: Dict[str, Any] = {}

    try:
        # Build email
        to_email = state.user_email or "example@gmail.com"
        subject = f"Patient Summary for Session {state.session_id}"
        body = getattr(state, "patient_summary_text", "Patient summary not generated.")

        service = get_gmail_service()
        draft = create_gmail_draft(service, to_email, subject, body)
        draft_id = draft.get("id")

        updates["gmail_draft_id"] = draft_id

        # Reasoning tracking
        reasoning_trail = getattr(state, "reasoning_trail", [])
        reasoning_trail.append(f"Gmail draft created: {draft_id}")
        updates["reasoning_trail"] = reasoning_trail

        # StageEvent (rich summary)
        stages = getattr(state, "stages", [])
        stages.append(StageEvent(
            code="gmail_draft",
            description="Draft email created in Gmail",
            data={
                "draft_id": draft_id,
                "summary": f"Draft ready to {to_email} with subject '{subject}'"
            }
        ))
        updates["stages"] = stages

        # Websocket push
        if ws_send:
            try:
                await ws_send({
                    "event_type": "node_update",
                    "node": "gmail_draft",
                    "payload": state.model_copy(update=updates).dict()
                })
            except Exception as e:
                logger.error(f"[GMAIL_DRAFT_NODE] WS send failed: {e}")

    except Exception as e:
        logger.error(f"[GMAIL_DRAFT_NODE] Failed to create draft: {e}")

    return updates
