# app/schemas_new/agentic_state.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class MissingInfoItem(BaseModel):
    term: str
    answered: bool = False
    user_input: Optional[str] = None

class ServiceCodeState(BaseModel):
    code: str
    severity: str  # fail, warn, pass
    missing_terms: List[MissingInfoItem] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

class StageEvent(BaseModel):
    """
    Represents a single workflow stage event.
    """
    code: str
    description: str
    data: Optional[Dict[str, Any]] = None

class AgenticState(BaseModel):
    soap_text: str
    predicted_service_codes: List[ServiceCodeState] = []
    reasoning_trail: List[str] = []
    waiting_for_user: bool = False
    candidates: Optional[List[Dict]] = None
    reranked_code: Optional[str] = None
    question: Optional[str] = None
    user_responses: Optional[Dict[str, Dict[str, str]]] = None
    pii_present: bool = False
    detected_pii: Optional[Any] = None
    loop_count: int = 0
    max_loops: int = 10
    anonymized_note: Optional[str] = None
    noop: Optional[bool] = None
    stages: List[StageEvent] = Field(default_factory=list)  # <-- new field
    session_id: str
    requires_referral_check: bool = False
    referral_required: Optional[bool] = None
    referral_rule_applied: Optional[str] = None
    patient_summary_pdf_path: Optional[str] = None



    def update(self, **kwargs: Any) -> 'AgenticState':
        """
        Updates the state with new values.

        Returns a new AgenticState instance with updated values.
        """
        return self.model_copy(update=kwargs)

class ServiceResponse(BaseModel):
    service_code: str
    answers: Dict[str, str]

class RespondRequest(BaseModel):
    responses: List[ServiceResponse]

class SubmitSOAPRequest(BaseModel):
    soap_text: str
    session_id: Optional[str] = None
