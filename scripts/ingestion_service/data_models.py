from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional

class ServiceCode(BaseModel):
    """
    A Pydantic model to represent a single Helfo service code.
    This ensures all data conforms to a specific structure.
    """
    name: str = Field(..., description="A short descriptive name in Norwegian.")
    required_terms: List[str] = Field(..., description="List of terms required in documentation (Norwegian keywords).")
    warn_terms: List[str] = Field(..., description="List of terms that if missing should trigger a warning.")
    suggestions: str = Field(..., description="User suggestions to improve documentation quality.")
    version: str = Field("HELFO-2025-01", description="The version of the service code rules.")
    requirement: str = Field(..., description="A short text summarizing the official requirement.")
    severity: dict = Field(..., description="A dictionary containing fail and warning messages.")

class ICD10Code(BaseModel):
    """
    A Pydantic model to represent a single ICD-10 diagnosis code from FinnKode.
    """
    code: str = Field(..., description="The ICD-10 diagnosis code.")
    name: str = Field(..., description="The official name of the diagnosis.")
    description: str = Field(..., description="A brief description of the diagnosis.")

class Status(BaseModel):
    """
    A Pydantic model for the pipeline's status endpoint.
    """
    status: str = "ok"
    last_run: Optional[str] = None
    message: str = "Pipeline is ready."