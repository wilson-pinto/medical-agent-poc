# #app/core/agentic_orchestrator.py
# from typing import List, Dict
# from app.core.search_service_codes import search_service_codes, get_service_code_descriptions
# from app.core.cross_encoder_rerank import rerank_candidates
# from app.core.search_diagnosis import search_diagnosis_with_explanation
# from app.core.validate_note_requirements.engine import validate_soap_against_rules
# from app.core.pii_pipeline import anonymize_soap
# from app.core.question_planner import plan_questions_from_missing
#
# class AgenticOrchestrator:
#     """
#     Stateful orchestrator for the agentic workflow:
#     - Predicts service codes
#     - Validates SOAP notes
#     - Extracts diagnoses
#     - Generates dynamic questions
#     - Anonymizes PII
#     """
#
#     def __init__(self):
#         self.state: Dict = {}  # To store ongoing workflow states
#
#     def predict_service_codes(self, soap_note: str) -> Dict:
#         # Step 1: Semantic search
#         candidates = search_service_codes(soap_note, top_k=10)
#
#         # Step 2: Cross-encoder rerank
#         reranked = rerank_candidates(soap_note, candidates)
#
#         codes = [r["service_code"] for r in reranked]  # updated key
#         reasoning = [r.get("reasoning", r.get("reason", "")) for r in reranked]
#
#         return {"codes": codes, "reasoning": reasoning}
#
#     def validate_soap(self, soap_note: str, service_codes: List[str]) -> Dict:
#         """
#         Validate SOAP note against HELFO rules and return per-code results.
#         """
#         results = validate_soap_against_rules(soap_note, service_codes)
#         # Convert PerCodeResult objects to dicts if needed
#         return {"service_code_states": [r.dict() if hasattr(r, "dict") else r for r in results]}
#
#     def extract_diagnoses(self, soap_note: str) -> Dict:
#         """
#         Extract diagnoses or concepts from the SOAP note.
#         """
#         concepts = []  # optionally extract concepts from note
#         return search_diagnosis_with_explanation(concepts)
#
#     def plan_questions(self, missing_terms: List[str]) -> List[Dict]:
#         """
#         Generate dynamic questions based on missing documentation terms.
#         """
#         return plan_questions_from_missing(missing_terms)
#
#     def anonymize_soap(self, soap_note: str) -> str:
#         """
#         Anonymize PII from SOAP note.
#         """
#         return anonymize_soap(soap_note)
# app/core/agentic_orchestrator.py
# # app/core/agentic_orchestrator.py
# from typing import List, Dict, Any
# from app.core.search_service_codes import search_service_codes, get_service_code_descriptions
# from app.core.cross_encoder_rerank import rerank_candidates
# from app.core.search_diagnosis import search_diagnosis_with_explanation
# from app.core.validate_note_requirements.engine import validate_soap_against_rules
# from app.core.pii_pipeline import anonymize_soap
# from app.core.question_planner import plan_questions_from_missing
# from app.schemas_new.agentic_state import AgenticState, MissingInfoItem
# from app.utils.logging import get_logger
#
# logger = get_logger(__name__)
#
# class AgenticOrchestrator:
#     """
#     Stateful orchestrator for the agentic workflow:
#     - Predicts service codes
#     - Validates SOAP notes
#     - Extracts diagnoses
#     - Generates dynamic questions
#     - Anonymizes PII
#     """
#
#     def __init__(self):
#         self.state: Dict = {}  # To store ongoing workflow states
#
#     def _merge_user_responses(self, state: AgenticState) -> None:
#         """
#         Merges user-provided answers into the original SOAP text.
#         This is a critical step to ensure subsequent validation checks
#         have the complete, updated note.
#         """
#         if state.user_responses and 'responses' in state.user_responses:
#             new_soap_parts = []
#             for response_item in state.user_responses['responses']:
#                 if 'answers' in response_item:
#                     for answer_text in response_item['answers'].values():
#                         new_soap_parts.append(answer_text)
#
#             # Append new answers to the original soap_text
#             if new_soap_parts:
#                 state.soap_text += " " + " ".join(new_soap_parts)
#                 logger.debug(f"Merged user responses. New SOAP text: {state.soap_text}")
#
#     def process_user_input(self, state: AgenticState, user_responses: Dict) -> AgenticState:
#         """
#         Handles user input and updates the state.
#         This is where the new merging logic is called.
#         """
#         # New log to check if this function is called and what data it receives
#         logger.info(f"Processing user input for session {state.session_id}. Received: {user_responses}")
#
#         # CRITICAL FIX: Store the user's responses in the state first.
#         state.user_responses = user_responses
#
#         self._merge_user_responses(state)
#
#         # We can also update the predicted_service_codes with the answered terms
#         if state.predicted_service_codes and state.user_responses and 'responses' in state.user_responses:
#             for response_item in state.user_responses['responses']:
#                 service_code = response_item.get('service_code')
#                 answers = response_item.get('answers', {})
#
#                 for sc in state.predicted_service_codes:
#                     if sc.code == service_code:
#                         for term_obj in sc.missing_terms:
#                             if term_obj.term in answers:
#                                 term_obj.answered = True
#                                 term_obj.user_input = answers[term_obj.term]
#                                 logger.debug(f"Marked term '{term_obj.term}' as answered.")
#
#         return state
#
#     def predict_service_codes(self, soap_note: str) -> Dict:
#         # Step 1: Semantic search
#         candidates = search_service_codes(soap_note, top_k=10)
#
#         # Step 2: Cross-encoder rerank
#         reranked = rerank_candidates(soap_note, candidates)
#
#         codes = [r["service_code"] for r in reranked]  # updated key
#         reasoning = [r.get("reasoning", r.get("reason", "")) for r in reranked]
#
#         return {"codes": codes, "reasoning": reasoning}
#
#     def validate_soap(self, soap_note: str, service_codes: List[str]) -> Dict:
#         """
#         Validate SOAP note against HELFO rules and return per-code results.
#         """
#         print("validate_soap is called")
#         results = validate_soap_against_rules(soap_note, service_codes)
#         # Convert PerCodeResult objects to dicts if needed
#         return {"service_code_states": [r.dict() if hasattr(r, "dict") else r for r in results]}
#
#     def extract_diagnoses(self, soap_note: str) -> Dict:
#         """
#         Extract diagnoses or concepts from the SOAP note.
#         """
#         concepts = []  # optionally extract concepts from note
#         return search_diagnosis_with_explanation(concepts)
#
#     def plan_questions(self, missing_terms: List[str]) -> List[Dict]:
#         """
#         Generate dynamic questions based on missing documentation terms.
#         """
#         return plan_questions_from_missing(missing_terms)
#
#     def anonymize_soap(self, soap_note: str) -> str:
#         """
#         Anonymize PII from SOAP note.
#         """
#         return anonymize_soap(soap_note)
#agentic_orchestrator.py
from typing import List, Dict, Any
from app.core.search_service_codes import search_service_codes, get_service_code_descriptions
from app.core.cross_encoder_rerank import rerank_candidates
from app.core.search_diagnosis import search_diagnosis_with_explanation
from app.core.validate_note_requirements.engine import validate_soap_against_rules
from app.core.pii_pipeline import anonymize_soap
from app.core.question_planner import plan_questions_from_missing
from app.schemas_new.agentic_state import AgenticState, MissingInfoItem
from app.utils.logging import get_logger

logger = get_logger(__name__)

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

    def _merge_user_responses(self, state: AgenticState) -> None:
        """
        Merges user-provided answers into the original SOAP text.
        This version correctly handles the simple term-to-answer dictionary.
        """
        logger.info("[MERGE] Starting merge of user responses.")
        # A quick safety check
        if not state.user_responses:
            logger.debug("[MERGE] No user responses found in state. Skipping merge.")
            return

        logger.info(f"[MERGE] Initial SOAP text: '{state.soap_text}'")
        logger.info(f"[MERGE] User responses to be merged: {state.user_responses}")

        new_soap_parts = []
        # This loop now correctly iterates over the simple dictionary structure
        for term, answer in state.user_responses.items():
            logger.debug(f"[MERGE] Processing term '{term}' with answer '{answer}'")
            # Append the response to the SOAP text in a readable format
            new_soap_parts.append(f"{term}: {answer}")

        # Join and append new answers to the original soap_text
        if new_soap_parts:
            merged_text = ". ".join(new_soap_parts) + "."
            state.soap_text += " " + merged_text
            logger.info(f"[MERGE] Successfully merged responses. New complete SOAP text: '{state.soap_text}'")
        else:
            logger.debug("[MERGE] No new SOAP parts were generated.")


    def process_user_input(self, state: AgenticState, user_responses: Dict) -> AgenticState:
        """
        Handles user input and updates the state.
        This is where the new merging logic is called.
        """
        # New log to check what data is received
        logger.info(f"[ORCHESTRATOR] Processing user input for session {state.session_id}. Received: {user_responses}")

        # CRITICAL FIX: Store the user's responses in the state first.
        state.user_responses = user_responses

        # Call the corrected merging logic
        self._merge_user_responses(state)

        # Update the predicted_service_codes with the answered terms
        logger.info("[ORCHESTRATOR] Updating 'missing_terms' status.")
        if state.predicted_service_codes:
            for sc in state.predicted_service_codes:
                if sc.missing_terms:
                    for term_obj in sc.missing_terms:
                        if term_obj.term in user_responses:
                            term_obj.answered = True
                            term_obj.user_input = user_responses[term_obj.term]
                            logger.info(f"[ORCHESTRATOR] Marked term '{term_obj.term}' as answered.")
                        else:
                            logger.debug(f"[ORCHESTRATOR] Term '{term_obj.term}' not found in user responses.")

        logger.info("[ORCHESTRATOR] User input processing complete. Returning updated state.")
        return state

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
        print("validate_soap is called")
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
