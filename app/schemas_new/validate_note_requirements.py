# app/schemas_new/validate_note_requirements.py

from pydantic import BaseModel
from typing import List, Optional

class PerCodeResult(BaseModel):
    """
    Represents the validation result for a single service code.
    """
    service_code: str
    compliance: str  # 'pass', 'warn', 'fail', 'unknown'
    missing_terms: List[str]
    suggestions: Optional[List[str]] = None
    gemini_used: bool = False
    gemini_reasoning: Optional[str] = None
    rule_version: Optional[str] = None

class CheckNoteResponse(BaseModel):
    """
    Overall validation result for multiple service codes in a SOAP note.
    """
    overall: str  # 'pass', 'partial', 'fail', 'unknown'
    results: List[PerCodeResult]
