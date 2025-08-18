#api.py
from fastapi import APIRouter
from app import config
from app.schemas import *
from app.core import rerank_gemini, rerank_openai, validation_gemini, diagnosis_search, service_search
from app.utils.json_utils import safe_extract_json
from app.core.pii_analyzer import analyze_text, anonymize_text
from fastapi import Query

from app.schemas import ClaimRejectionRequest, ClaimRejectionResponse
from app.core.claim_learning_engine import learn_from_rejection
from app.schemas_new.validate_note_requirements import CheckNoteRequest, CheckNoteResponse, PerCodeResult
from app.core.validate_note_requirements.engine import validate_soap_against_codes
from app.core.claim_learning_engine import lookup_learned_failure

from app.core.predict_helpers import (
    get_similar_failures,
    calculate_rejection_probability,
    assign_risk_level,
    aggregate_suggestions
)

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

@router.post("/ai/claim-rejection/learn", response_model=ClaimRejectionResponse)
def claim_rejection_learn(req: ClaimRejectionRequest):
    return learn_from_rejection(req)

@router.post("/ai/v3/self-learned-check-note-requirements", response_model=CheckNoteResponse)
def self_learned_check(req: CheckNoteRequest):
    """
    Enhanced version of v2: first checks whether a similar SOAP+codes
    has previously been rejected and learned by the system.
    If yes → fail immediately and return suggestions learned from past.
    Else → run normal engine.
    """
    learned = lookup_learned_failure(req.soap, req.service_codes)
    if learned:
        # Fetch the original validation results from DB or reconstruct minimal results
        # Here, we build dummy PerCodeResult objects per service code
        learned_suggestions = learned.get("suggestions", [])
        results = [
            PerCodeResult(
                service_code=code,
                compliance="fail",
                missing_terms=[],
                suggestions=learned_suggestions,
                gemini_used=False,
                gemini_reasoning="Overridden by self-learning model.",
                rule_version=None
            )
            for code in req.service_codes
        ]
        return CheckNoteResponse(
            overall="fail",
            results=results
        )
    analysis_dict = validate_soap_against_codes(req.soap, req.service_codes)
    response_obj = CheckNoteResponse(**analysis_dict)
    return response_obj

@router.post("/ai/predict-claim-outcome", response_model=ClaimPredictionResponse)
def predict_claim_outcome(req: CheckNoteRequest):
    # Step 1: Analyze & anonymize the SOAP note
    entities = analyze_text(req.soap)
    anon_soap = anonymize_text(req.soap, entities)

    # Step 2: Find similar past failures using anonymized SOAP
    similar_failures = get_similar_failures(anon_soap, req.service_codes)

    # Step 3: Calculate rejection probability
    rejection_prob = calculate_rejection_probability(similar_failures)

    # Step 4: Assign risk level
    risk_level = assign_risk_level(rejection_prob)

    # Step 5: Aggregate suggestions from similar failures
    suggestions = aggregate_suggestions(similar_failures)

    # Step 6: Estimate reimbursement
    base_reimbursement = 1000.0
    estimated_reimbursement = base_reimbursement * (1.0 - rejection_prob)

    # Step 7: Enhanced reasoning message with debugging info
    num_similar = len(similar_failures)
    if num_similar == 0:
        reasoning = "Low risk: No similar past failures found in learning database."
    else:
        scores = [f["score"] for f in similar_failures]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)

        reasoning = (
            f"{risk_level.title()} risk: Found {num_similar} similar failure(s). "
            f"Similarity scores: avg={avg_score:.3f}, max={max_score:.3f}. "
            f"Calculated rejection probability: {rejection_prob:.3f}"
        )

    return ClaimPredictionResponse(
        rejection_probability=rejection_prob,
        risk_level=risk_level,
        suggestions=suggestions,
        reasoning=reasoning,
        estimated_reimbursement=estimated_reimbursement
    )

# Add a debugging endpoint
@router.post("/ai/predict-claim-outcome/debug")
def predict_claim_outcome_debug(req: CheckNoteRequest):
    """Debug version that shows detailed breakdown"""
    entities = analyze_text(req.soap)
    anon_soap = anonymize_text(req.soap, entities)

    # Get detailed breakdown
    breakdown = get_risk_breakdown(anon_soap, req.service_codes)

    return {
        "anonymized_soap": anon_soap,
        "breakdown": breakdown,
        "faiss_index_size": FAISS_INDEX.ntotal,
        "service_codes": req.service_codes
    }
