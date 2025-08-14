#app/schemas_new/agentic_state.py
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from pydantic import BaseModel
from typing import Dict, List

class MissingInfoItem(BaseModel):
    term: str
    answered: bool = False
    user_input: Optional[str] = None

class ServiceCodeState(BaseModel):
    code: str
    severity: str  # fail, warn, pass
    missing_terms: List[MissingInfoItem] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

class AgenticState(BaseModel):
    soap_text: str
    predicted_service_codes: List[ServiceCodeState]
    reasoning_trail: List[str]
    waiting_for_user: bool = False
    candidates: Optional[List[Dict]] = None
    reranked_code: Optional[Dict] = None
    question: Optional[str] = None          # <-- add this
    user_responses: Optional[Dict[str, Dict[str, str]]] = None  # <-- change here
    loop_count: int = 0                     # <-- new
    max_loops: int = 10                     # <-- new



class ServiceResponse(BaseModel):
    service_code: str
    answers: Dict[str, str]

class RespondRequest(BaseModel):
    responses: List[ServiceResponse]

