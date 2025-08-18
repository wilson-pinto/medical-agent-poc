#api.py
from fastapi import APIRouter
from app import config
from app.schemas import *
from app.core import rerank_gemini, rerank_openai, validation_gemini, diagnosis_search, service_search
from app.utils.json_utils import safe_extract_json
from app.core.pii_analyzer import analyze_text, anonymize_text
from fastapi import Query

from app.schemas_new.validate_note_requirements import CheckNoteRequest, CheckNoteResponse
from app.core.validate_note_requirements.engine import validate_soap_against_codes

router = APIRouter()

@router.post("/ai/suggest-service-codes/local-model",
summary="Suggest HELFO service codes from SOAP notes using local embedding model"
)
def search_agent(payload: QueryRequest):
    matches = service_search.search_codes(payload.query, payload.top_k)
    return {"session_id": payload.session_id, "candidates": matches}

@router.post("/agent/rerank/invoke")
def rerank_agent(payload: RerankRequest):
    if config.USE_GEMINI:
        decision = rerank_gemini.get_best_code(payload.query, payload.candidates)
    else:
        decision = rerank_openai.rerank_with_openai(payload.query, payload.candidates)
    return {"session_id": payload.session_id, "decision": decision}

# @router.post("/ai/check-note-requirements")
# def check_note_requirements_api(payload: NoteCheckRequest):
#     return {"result": validation_gemini.check_note_requirements(payload.soap, payload.service_codes)}

@router.post("/ai/suggest-service-codes",
summary="Suggest HELFO service codes from SOAP notes using Gemini LLM"
)
def suggest_service_codes(payload: QueryRequest):
    candidates = service_search.search_codes(payload.query)
    if config.USE_GEMINI:
        decision = rerank_gemini.get_best_code(payload.query, candidates, payload.top_k)
    else:
        decision = rerank_openai.rerank_with_openai(payload.query, candidates)
    return {"session_id": payload.session_id, "decision": decision}


@router.post("/ai/extract-diagnoses")
def extract_diagnoses(
    payload: SoapInput,
    top_k: int = Query(5, ge=1, le=10, description="Number of top matches per concept before rerank"),
    min_similarity: float = Query(0.6, ge=0.0, le=1.0, description="Minimum similarity threshold"),
    final_top_n: int = Query(1, ge=1, le=10, description="Number of top matches to keep per concept after rerank")
):
    """
    Extract probable diagnoses from SOAP note.

    This endpoint:
    - Removes PII from SOAP.
    - Uses Gemini LLM to group clinical concepts from the SOAP.
    - Searches for matching diagnoses for each concept.
    - Uses Gemini LLM to rerank and filter diagnoses.
    """
    result = validation_gemini.extract_diagnoses_from_soap(
        payload.soap,
        top_k=top_k,
        min_similarity=min_similarity,
        final_top_n=final_top_n
    )
    return result

@router.post("/ai/check-service-diagnosis")
def check_service_diagnosis(payload: ServiceDiagnosisInput):
    result = validation_gemini.check_service_diagnosis(payload.soap, payload.diagnoses, payload.service_codes)
    return {"results": result}

@router.post("/semantic-combo-warning")
def semantic_combo_warning(payload: ComboInput):
    warnings = validation_gemini.check_semantic_combo_warning(payload.service_codes, payload.soap)
    return {"warnings": warnings}

@router.post("/diagnosis/search/invoke/local-embedding-model")
def diagnosis_search_api(payload: DiagnosisSearchRequest):
    return {"results": diagnosis_search.search_diagnosis(payload.query, payload.top_k)}

@router.post("/pii/analyze")
def analyze_pii(input: PiiTextInput):
    entities = analyze_text(input.text)
    return {"entities": entities}

@router.post("/pii/anonymize")
def anonymize_pii(input: PiiTextInput):
    entities = analyze_text(input.text)
    redacted = anonymize_text(input.text, entities)
    return {"anonymized_text": redacted}

@router.post("/ai/v2/check-note-requirements", response_model=CheckNoteResponse)
def check_note(req: CheckNoteRequest):
    result = validate_soap_against_codes(req.soap, req.service_codes)
    # result already matches {"overall":..., "results":[PerCodeResult,...]}
    # Ensure results serialization (Pydantic will handle PerCodeResult)
    return result