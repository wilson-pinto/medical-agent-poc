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

# NEW: Pydantic model for the XML Taksttabell data
class TakstKode(BaseModel):
    """
    A Pydantic model to represent a single takst code from the Taksttabell XML.
    This includes detailed metadata like fees, valid dates, and combinations.
    """
    takstkode: str = Field(..., description="The official tariff code.")
    fradato: str = Field(..., description="The start date of validity (YYYY-MM-DD).")
    tildato: str = Field(..., description="The end date of validity (YYYY-MM-DD).")
    honorar: float = Field(..., description="The total fee for the service.")
    refusjon: float = Field(..., description="The reimbursement portion of the fee.")
    egenandel: float = Field(..., description="The patient's deductible portion of the fee.")
    ugyldigKombinasjon: List[str] = Field(default_factory=list, description="List of codes that cannot be combined with this one.")
    kreverTakst: List[str] = Field(default_factory=list, description="List of codes required to be used with this one.")
    kreverProsedyre: List[str] = Field(default_factory=list, description="List of procedure codes required with this one.")
    kreverDiagnose: List[str] = Field(default_factory=list, description="List of diagnosis codes required with this one.")
    minimumTidsbruk: Optional[int] = Field(None, description="Minimum time in minutes for the service.")
    beskrivelse: str = Field(..., description="The official description of the tariff code.")
    merknadNr: Optional[str] = Field(None, description="The code for the official note.")
    merknadTekst: Optional[str] = Field(None, description="The text of the official note.")
