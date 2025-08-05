from fastapi import APIRouter
from app import config
from app.schemas import *
from app.core import rerank_gemini, rerank_openai, validation_gemini, diagnosis_search, service_search
from app.utils.json_utils import safe_extract_json

router = APIRouter()

@router.post("/agent/search/localmodel/invoke")
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

@router.post("/ai/check-note-requirements")
def check_note_requirements_api(payload: NoteCheckRequest):
    return {"result": validation_gemini.check_note_requirements(payload.soap, payload.service_codes)}

@router.post("/ai/extract-diagnoses")
def extract_diagnoses(payload: SoapInput):
    return {"diagnoses": validation_gemini.extract_diagnoses_from_soap(payload.soap)}

@router.post("/ai/check-service-diagnosis")
def check_service_diagnosis(payload: ServiceDiagnosisInput):
    result = validation_gemini.check_service_diagnosis(payload.soap, payload.diagnoses, payload.service_codes)
    return {"results": result}

@router.post("/semantic-combo-warning")
def semantic_combo_warning(payload: ComboInput):
    warnings = validation_gemini.check_semantic_combo_warning(payload.service_codes, payload.soap)
    return {"warnings": warnings}

@router.post("/diagnosis/search/invoke")
def diagnosis_search_api(payload: DiagnosisSearchRequest):
    return {"results": diagnosis_search.search_diagnosis(payload.query, payload.top_k)}
