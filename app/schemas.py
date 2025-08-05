from pydantic import BaseModel
from typing import List

class QueryRequest(BaseModel):
    session_id: str
    query: str
    top_k: int = 5

class RerankRequest(BaseModel):
    session_id: str
    query: str
    candidates: List[str]

class NoteCheckRequest(BaseModel):
    soap: str
    service_codes: List[str]

class SoapInput(BaseModel):
    soap: str

class ServiceDiagnosisInput(BaseModel):
    soap: str
    diagnoses: List[str]
    service_codes: List[str]

class ComboInput(BaseModel):
    soap: str
    service_codes: List[str]

class DiagnosisSearchRequest(BaseModel):
    query: str
    top_k: int = 5