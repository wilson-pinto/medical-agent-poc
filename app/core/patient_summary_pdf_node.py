import io
import base64
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from typing import Dict, Any, Optional, Callable
from app.schemas_new.agentic_state import AgenticState, StageEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)

async def patient_summary_pdf_node(
 state: AgenticState,
 ws_send: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> Dict[str, Any]:
 updates: Dict[str, Any] = {}

 pdf_buffer = io.BytesIO()
 c = canvas.Canvas(pdf_buffer, pagesize=letter)
 text_object = c.beginText(50, 700)
 text_object.setFont("Helvetica", 12)

 summary = getattr(state, "patient_summary", "No summary available.")
 for line in summary.split("\n"):
     text_object.textLine(line)

 c.drawText(text_object)
 c.showPage()
 c.save()

 pdf_buffer.seek(0)
 pdf_bytes = pdf_buffer.read()
 pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

 updates["patient_summary_pdf"] = pdf_b64

 # Append stage
 stages = getattr(state, "stages", [])
 stages.append(StageEvent(
     code="patient_summary_pdf",
     description="Generated patient summary PDF",
     data={"patient_summary_pdf": pdf_b64}
 ))
 updates["stages"] = stages

 # Send WebSocket update for download
 if ws_send:
     try:
         await ws_send({
             "event_type": "pdf_ready",
             "payload": {"pdf_base64": pdf_b64, "filename": f"patient_summary_{state.session_id}.pdf"}
         })
     except Exception as e:
         logger.error(f"[PATIENT_PDF_NODE] Failed sending ws update: {e}")

 return updates
