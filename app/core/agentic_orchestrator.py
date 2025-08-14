from typing import List, Dict
from app.core.search_service_codes import search_service_codes, get_service_code_descriptions
from app.core.cross_encoder_rerank import rerank_candidates
from app.core.search_diagnosis import search_diagnosis_with_explanation
from app.core.validate_note_requirements.engine import validate_soap_against_rules
from app.core.pii_pipeline import anonymize_soap
from app.core.question_planner import plan_questions_from_missing

class AgenticOrchestrator:
    """
    Stateful orchestrator for the agentic workflow:
    - Predicts service codes
    - Validates SOAP notes
    - Extracts diagnoses
    - Generates dynamic questions
    - Anonymizes PII
    """

    def __init__(self):
        self.state: Dict = {}  # To store ongoing workflow states

    def predict_service_codes(self, soap_note: str) -> Dict:
        # Step 1: Semantic search
        candidates = search_service_codes(soap_note, top_k=10)

        # Step 2: Cross-encoder rerank
        reranked = rerank_candidates(soap_note, candidates)

        codes = [r["service_code"] for r in reranked]  # updated key
        reasoning = [r.get("reasoning", r.get("reason", "")) for r in reranked]

        return {"codes": codes, "reasoning": reasoning}

    def validate_soap(self, soap_note: str, service_codes: List[str]) -> Dict:
        """
        Validate SOAP note against HELFO rules and return per-code results.
        """
        results = validate_soap_against_rules(soap_note, service_codes)
        # Convert PerCodeResult objects to dicts if needed
        return {"service_code_states": [r.dict() if hasattr(r, "dict") else r for r in results]}

    def extract_diagnoses(self, soap_note: str) -> Dict:
        """
        Extract diagnoses or concepts from the SOAP note.
        """
        concepts = []  # optionally extract concepts from note
        return search_diagnosis_with_explanation(concepts)

    def plan_questions(self, missing_terms: List[str]) -> List[Dict]:
        """
        Generate dynamic questions based on missing documentation terms.
        """
        return plan_questions_from_missing(missing_terms)

    def anonymize_soap(self, soap_note: str) -> str:
        """
        Anonymize PII from SOAP note.
        """
        return anonymize_soap(soap_note)
