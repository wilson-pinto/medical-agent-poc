#app/schemas_new/agentic_state.py
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from pydantic import BaseModel
from typing import Dict, List
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

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
    predicted_service_codes: List[ServiceCodeState] = []
    reasoning_trail: List[str] = []
    waiting_for_user: bool = False
    candidates: Optional[List[Dict]] = None
    reranked_code: Optional[Dict] = None
    question: Optional[str] = None
    user_responses: Optional[Dict[str, Dict[str, str]]] = None
    pii_present: bool = False
    detected_pii: Optional[Any] = None
    loop_count: int = 0
    max_loops: int = 10
    anonymized_note: Optional[str] = None
    noop: Optional[bool] = None

#     current_service_code: Optional[str] = None
    session_id: str

    def update(self, **kwargs: Any) -> 'AgenticState':
        """
        Updates the state with new values.

        This method allows for updating one or more fields of the AgenticState
        object by passing them as keyword arguments. It creates a new instance
        of the class with the updated values, ensuring the object remains
        immutable and thread-safe.

        Returns:
            A new AgenticState instance with the updated values.
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

