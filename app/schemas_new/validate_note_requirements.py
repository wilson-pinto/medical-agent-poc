# app/schemas_new/validate_note_requirements.py
from pydantic import BaseModel
from typing import List, Optional, Dict

class CheckNoteRequest(BaseModel):
    soap: str
    service_codes: List[str]

class PerCodeResult(BaseModel):
    service_code: str
    compliance: str                     # 'pass', 'warn', 'fail', or 'unknown'
    missing_terms: Optional[List[str]]
    suggestions: Optional[List[str]]
    gemini_used: bool
    gemini_reasoning: Optional[str] = None
    rule_version: Optional[str] = None


class CheckNoteResponse(BaseModel):
    overall: str                         # 'pass' / 'partial' / 'fail' / 'unknown'
    results: List[PerCodeResult]
