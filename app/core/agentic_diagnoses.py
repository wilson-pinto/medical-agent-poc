import logging
import json
import re
from typing import List, Dict, Any

import google.generativeai as genai

from app.config import GEMINI_API_KEY
from app.core.diagnosis_search import search_diagnosis_with_explanation
from app.core.pii_analyzer import analyze_text, anonymize_text
from app.core.validation_gemini import group_clinical_concepts_with_gemini

# Configure Gemini at the module level with the correct model name
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

logger = logging.getLogger(__name__)

# --- Utility to safely extract JSON from text ---
def safe_extract_json(text: str) -> str | None:
    """
    Attempts to find and extract a JSON object or array from a string.
    This helps when the LLM wraps the JSON in conversational text.
    """
    try:
        # Use a regular expression to find a JSON array (starts with [ and ends with ])
        # The re.DOTALL flag allows . to match newlines
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return match.group(0)
    except re.error as e:
        logger.error(f"Regex error in safe_extract_json: {e}")
    return None

# --- Concept-based Judgment & Explanation Prompt ---
FINAL_JUDGMENT_PROMPT_TEMPLATE = """You are an expert medical diagnostician.

Given a patient's clinical notes and a list of key clinical concepts, your task is to assign the most appropriate diagnosis code to each concept.

For each concept, select the single best-fitting diagnosis code from the candidate list that is most relevant to that specific concept. Your final choices must come from the provided list of candidates.

Analyze the full SOAP note to understand the context, then choose the most relevant code for each concept.

✳️ Output format:
- A JSON array of objects.
- Each object in the array must have three fields: "concept", "code", and "explanation".
- "explanation" should be a clear and concise reason for your choice, linking the code directly to the concept.
- **IMPORTANT**: Provide **ONLY** the JSON array as your response, without any additional text, markdown, or commentary.

Full SOAP Note:
{soap_note}

Clinical Concepts:
{clinical_concepts}

Top Candidate Diagnoses (from semantic search, for all concepts combined):
{candidate_diagnoses}
"""

def final_diagnoses_judgment(
    soap_note: str,
    grouped_concepts: List[str],
    search_results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Step 5: Uses Gemini LLM to assign a diagnosis code to each clinical concept.

    Args:
        soap_note: The original (anonymized) SOAP note.
        grouped_concepts: A list of the key clinical concepts from the note.
        search_results: The output from the hybrid search, containing reranked candidates.

    Returns:
        A list of dictionaries, where each dictionary contains a concept, its assigned code, and an explanation.
    """
    if not model:
        logger.error("Gemini model not initialized. Please check GEMINI_API_KEY.")
        return [{"code": None, "explanation": "Gemini API key is missing or invalid."}]

    # Prepare the list of all top candidates from the search results
    all_candidates = []
    for concept_block in search_results.get("diagnoses", []):
        for match in concept_block.get("matches", []):
            if {"code": match.get("code"), "description": match.get("description")} not in all_candidates:
                all_candidates.append({
                    "code": match.get("code"),
                    "description": match.get("description")
                })

    # Build the prompt for the LLM
    prompt = FINAL_JUDGMENT_PROMPT_TEMPLATE.format(
        soap_note=soap_note,
        clinical_concepts=json.dumps(grouped_concepts, indent=2),
        candidate_diagnoses=json.dumps(all_candidates, indent=2)
    )

    try:
        # Call the LLM to make the judgments
        response = model.generate_content(prompt)

        # We need to manually parse the response text, which should be a JSON string
        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        # Safely extract the JSON part in case the model adds extra text
        json_text = safe_extract_json(response.text)
        if not json_text:
            raise ValueError("Could not find a valid JSON array in the response.")

        final_results = json.loads(json_text)

        # Basic validation of the output
        if not isinstance(final_results, list) or not all("code" in item for item in final_results):
            logger.warning("Gemini did not return the expected JSON list. Falling back.")
            return [{"concept": "Overall", "code": all_candidates[0].get("code") if all_candidates else None, "explanation": "Fallback: LLM output was unexpected."}]

        return final_results

    except Exception as e:
        logger.exception("Final diagnoses judgment failed.")
        # Fallback to a simple result if any part of the process fails
        top_candidates = [m for cb in search_results.get("diagnoses", []) for m in cb.get("matches", [])]
        fallback_code = top_candidates[0]["code"] if top_candidates else "N/A"
        return [{
            "concept": "Overall",
            "code": fallback_code,
            "explanation": f"Agentic flow failed at the final judgment step due to error: {e}. This is a fallback to the top reranked code."
        }]


def run_agentic_diagnosis_flow(
    soap_note: str,
    initial_k: int = 50,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Main function to run the full agentic diagnosis code extraction flow.

    Args:
        soap_note: The raw SOAP note text.
        initial_k: Number of candidates for the initial FAISS retrieval.
        top_k: Number of final results to consider after reranking.

    Returns:
        A list of dictionaries containing the assigned diagnosis code and a detailed explanation for each concept.
    """
    # --- Step 1: PII Removal ---
    try:
        entities = analyze_text(soap_note)
        anonymized_note = anonymize_text(soap_note, entities)
        logger.debug("Step 1: PII removed.")
    except Exception:
        logger.exception("PII removal failed, using original SOAP.")
        anonymized_note = soap_note

    # --- Step 2: Clinical Concept Grouping ---
    try:
        grouped_concepts = group_clinical_concepts_with_gemini(anonymized_note)
        logger.debug(f"Step 2: Grouped {len(grouped_concepts)} concepts.")
    except Exception:
        logger.exception("Concept grouping failed, using whole note as single concept.")
        grouped_concepts = [anonymized_note.strip()]

    # --- Step 3 & 4: Initial Retrieval and Contextual Reranking ---
    try:
        search_results = search_diagnosis_with_explanation(
            grouped_concepts=grouped_concepts,
            initial_k=initial_k,
            top_k=top_k
        )
        logger.debug("Step 3 & 4: Hybrid RAG retrieval and reranking complete.")
    except Exception:
        logger.exception("Hybrid RAG search failed.")
        return [{"concept": "Overall", "code": None, "explanation": "Failed to retrieve diagnosis codes."}]

    # --- Step 5: Final Judgment & Explanation for each concept ---
    try:
        final_result = final_diagnoses_judgment(anonymized_note, grouped_concepts, search_results)
        logger.debug("Step 5: Final judgment for each concept complete.")
    except Exception:
        logger.exception("Final judgment step failed.")
        # Fallback if the final LLM step fails
        top_candidates = [m for cb in search_results.get("diagnoses", []) for m in cb.get("matches", [])]
        fallback_code = top_candidates[0]["code"] if top_candidates else "N/A"
        final_result = [{
            "concept": "Overall",
            "code": fallback_code,
            "explanation": "Agentic flow failed at the final judgment step. This is a fallback to the top reranked code."
        }]

    return final_result

# --- Example Usage (for testing) ---
if __name__ == "__main__":
    test_soap_note = """
    Patient John Doe, DOB 1990-05-15.
    Subjective: The patient reports a persistent cough that started three days ago, along with a mild fever. The cough is dry and has not improved. He denies any chest pain or shortness of breath.
    Objective: Patient is afebrile at 37.2°C. Lungs are clear on auscultation. Throat is slightly red but no exudate.
    Assessment: Possible viral upper respiratory infection.
    Plan: Advised to rest, stay hydrated, and use over-the-counter medication.
    """

    print("--- Running Agentic Diagnosis Flow with a sample SOAP note ---")
    result = run_agentic_diagnosis_flow(test_soap_note)
    print(json.dumps(result, indent=2))
    print("--- Flow Complete ---")
