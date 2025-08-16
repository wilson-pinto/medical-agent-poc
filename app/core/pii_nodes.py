# app/core/pii_nodes.py
from typing import Dict, Any
from datetime import datetime
from functools import wraps
from presidio_analyzer import RecognizerResult

from app.schemas_new.agentic_state import AgenticState
from app.utils.logging import get_logger
from app.core.pii_analyzer import analyze_text, anonymize_text

logger = get_logger(__name__)

# ----------------------------
# Decorator for timestamped logging
# ----------------------------
def timestamped(func):
    """
    Logs function calls with timestamps.
    Works for both sync and async functions.
    """
    import asyncio

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        ts_str = datetime.now().strftime("[%H:%M:%S]")
        logger.info(f"{ts_str} {func.__name__} called")
        return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        ts_str = datetime.now().strftime("[%H:%M:%S]")
        logger.info(f"{ts_str} {func.__name__} called")
        return func(*args, **kwargs)

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

# ----------------------------
# PII Detection Node
# ----------------------------
@timestamped
def pii_detection_node(state: AgenticState) -> Dict[str, Any]:
    state.reasoning_trail.append(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for PII")

    detected_pii_results = analyze_text(state.soap_text)
    pii_present = bool(detected_pii_results)

    detected_pii = [
        {"entity_type": e.entity_type, "start": e.start, "end": e.end}
        for e in detected_pii_results
    ]

    state.reasoning_trail.append(
        f"[{datetime.now().strftime('%H:%M:%S')}] pii_detection_node: "
        f"PII detected = {pii_present}, entities = {detected_pii}"
    )
    logger.info(f"PII Detected: {pii_present} | Entities: {detected_pii}")

    return {
        "pii_present": pii_present,
        "detected_pii": detected_pii,
        "reasoning_trail": state.reasoning_trail
    }

# ----------------------------
# PII Anonymization Node
# ----------------------------
@timestamped
def anonymize_pii_node(state: AgenticState) -> Dict[str, Any]:
    state.reasoning_trail.append(f"[{datetime.now().strftime('%H:%M:%S')}] Anonymizing PII")

    soap_note = state.soap_text
    detected_pii = state.detected_pii or []

    recognizer_results = [
        RecognizerResult(
            entity_type=item["entity_type"],
            start=item["start"],
            end=item["end"],
            score=0.5
        )
        for item in detected_pii
    ]

    if recognizer_results:
        anonymized_note = anonymize_text(soap_note, recognizer_results)
        pii_status = "PII has been anonymized."
    else:
        anonymized_note = soap_note
        pii_status = "No PII to anonymize."

    state.reasoning_trail.append(f"[{datetime.now().strftime('%H:%M:%S')}] anonymize_pii_node: {pii_status}")
    logger.info(pii_status)

    return {
        "soap_text": anonymized_note,
        "reasoning_trail": state.reasoning_trail
    }
