import re
import json
import logging
from typing import List

import google.generativeai as genai

from app.config import GEMINI_API_KEY
from app.utils.json_utils import safe_extract_json
from app.core.diagnosis_search import search_diagnosis_with_explanation
from app.core.pii_analyzer import analyze_text, anonymize_text

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

logger = logging.getLogger(__name__)

# ----------------------------
# Helpers: model + parsing utils
# ----------------------------
def _get_response_text(resp) -> str:
    """
    Extract raw text from Gemini API response regardless of format.
    Handles string, dict, and structured parts.
    """
    if hasattr(resp, "text") and isinstance(resp.text, str):
        return resp.text
    try:
        # Try candidates/parts
        parts = resp.candidates[0].content.parts
        for p in parts:
            if hasattr(p, "text") and isinstance(p.text, str):
                return p.text
            elif hasattr(p, "text") and isinstance(p.text, dict):
                return json.dumps(p.text)
    except Exception:
        pass
    # As a last resort, try direct dict dump
    try:
        return json.dumps(resp)
    except Exception:
        return ""

def _clean_model_text(text: str) -> str:
    """
    Remove markdown/json fences and surrounding whitespace.
    """
    if not text:
        return ""
    if not isinstance(text, str):
        text = json.dumps(text)
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return cleaned.strip()

def _extract_first_json_array(text: str) -> List:
    """
    Finds the first JSON array in the text and returns it as Python list.
    Returns [] on failure.
    """
    if not text:
        return []
    m = re.search(r"(\[[^\]]*\])", text, flags=re.DOTALL)
    if not m:
        return []
    fragment = m.group(1)
    try:
        return json.loads(fragment)
    except json.JSONDecodeError:
        try:
            cleaned = re.sub(r",\s*(\]|})", r"\1", fragment)
            return json.loads(cleaned)
        except Exception:
            logger.exception("Failed to json-decode array fragment.")
            return []

# ----------------------------
# New Gemini-based grouping / concept extraction
# ----------------------------
GROUPING_PROMPT_TEMPLATE = """You are an expert clinical coder. Your task is to analyze a clinical note and extract the most clinically meaningful and granular concepts, including symptoms, findings, and diagnoses. For each concept, provide the most specific ICD-10 code and a brief, one-sentence explanation for your choice.

Follow these strict rules:
1. Treat **clinical findings** (symptoms, measurements, and observations) and **clinical diagnoses** as separate, distinct concepts.
2. Never combine a finding and a diagnosis into a single concept.
3. Include important modifiers such as duration, severity, frequency, or other relevant attributes **within** the main clinical concept rather than as separate concepts. For example, do not extract “duration of diarrhea” separately from “diarrhea.”
4. Your output must be in JSON format.

### Clinical Note:
{soap}

### Output Format (JSON Array of Objects):
[
  {{
    "concept": "A granular clinical concept from the note",
    "code": "The most specific ICD-10 code (e.g., M54.5)",
    "explanation": "A one-sentence reason for this code choice."
  }}
]
"""

def group_clinical_concepts_with_gemini(soap_text: str) -> list:
    """
    Use Gemini to extract and group clinical concepts from the SOAP note.
    Returns a list of dicts with keys: concept, code, explanation.
    """
    prompt = GROUPING_PROMPT_TEMPLATE.format(soap=soap_text)
    try:
        response = model.generate_content(prompt)
        raw_text = _get_response_text(response)
        logger.debug(f"Gemini grouping response: {raw_text}")
        text = _clean_model_text(raw_text)
        concepts = _extract_first_json_array(text)
        if not concepts:
            logger.warning("Gemini returned empty or invalid JSON for grouping; falling back to whole SOAP.")
            return [{"concept": soap_text.strip(), "code": "", "explanation": ""}]
        return concepts
    except Exception:
        logger.exception("Gemini grouping failed, falling back to whole SOAP.")
        return [{"concept": soap_text.strip(), "code": "", "explanation": ""}]

# ----------------------------
# Gemini reranking for diagnoses
# ----------------------------
def rerank_diagnoses_with_gemini(grouped_concepts: List[str], search_results: dict, final_top_n: int = 1):
    updated_results = []
    for concept_block in search_results.get("diagnoses", []):
        concept = concept_block["concept"]

        # 🔹 Ensure concept is a string (fixes .strip() error)
        if isinstance(concept, dict):
            concept = concept.get("concept", json.dumps(concept))
        else:
            concept = str(concept)

        matches = concept_block["matches"]

        prompt = f"""
You are a medical expert assistant with deep clinical knowledge.

Given the clinical concept below (which may include explicit negations or symptom absences), you are provided a list of possible diagnosis codes and descriptions with similarity scores derived from text embeddings.

Your tasks:
- Evaluate each diagnosis in the context of the full clinical concept.
- Prioritize diagnoses that are clinically plausible and explainable by the symptoms and findings.
- Exclude diagnoses that are unrelated or unlikely given the symptom pattern.
- Consider classic symptoms, absence of expected symptoms, and differential diagnosis principles.
- Provide a ranked list of the most relevant diagnoses with a brief clinical reason for inclusion.
- Output a JSON array with fields: code, description, reason (brief), similarity, rank.

Clinical concept:
\"\"\"{concept}\"\"\"

Possible diagnoses:
{json.dumps(matches, indent=2)}

Output only the JSON array.
"""
        try:
            logger.debug(f"Prompt for Gemini rerank for concept: {concept}")
            resp = model.generate_content(prompt)
            raw_text = _get_response_text(resp)
            logger.debug(f"[DEBUG] Gemini raw response for concept '{concept}': {raw_text}")
            text = _clean_model_text(raw_text)

            try:
                filtered = safe_extract_json(text)
            except Exception:
                logger.warning(f"Failed to parse Gemini response JSON, falling back to original matches for concept: {concept}")
                filtered = matches

            filtered = filtered[:final_top_n]
            for i, diag in enumerate(filtered):
                diag['rank'] = i + 1

            updated_results.append({
                "concept": concept,
                "matches": filtered
            })
        except Exception:
            logger.exception(f"Gemini reranking failed for concept: {concept}")
            updated_results.append({
                "concept": concept,
                "matches": matches[:final_top_n]
            })
    return updated_results

# ----------------------------
# Main extraction function
# ----------------------------
def extract_diagnoses_from_soap(soap: str, top_k: int = 5, min_similarity: float = 0.6, final_top_n: int = 1):
    try:
        entities = analyze_text(soap)
        soap_no_pii = anonymize_text(soap, entities)
    except Exception:
        logger.exception("PII removal failed; falling back to original SOAP.")
        soap_no_pii = soap

    try:
        grouped = group_clinical_concepts_with_gemini(soap_no_pii)
        logger.debug(f"[DEBUG] Gemini grouped clinical concepts ({len(grouped)}): {grouped}")
    except Exception:
        logger.exception("Gemini grouping failed; using whole SOAP as single concept.")
        grouped = [{"concept": soap_no_pii.strip(), "code": "", "explanation": ""}]

    grouped_concept_texts = [
        item["concept"] if isinstance(item, dict) and "concept" in item else str(item)
        for item in grouped
    ]

    try:
        search_results = search_diagnosis_with_explanation(
            grouped_concepts=grouped_concept_texts, top_k=top_k, min_similarity=min_similarity
        )
    except Exception:
        logger.exception("search_diagnosis_with_explanation failed.")
        return {"unique_codes": [], "detailed_matches": []}

    try:
        detailed_matches = rerank_diagnoses_with_gemini(
            grouped_concepts=grouped_concept_texts,
            search_results=search_results,
            final_top_n=final_top_n
        )
    except Exception:
        logger.exception("Gemini reranking failed, using original matches.")
        detailed_matches = search_results.get("diagnoses", [])

    unique_codes = {
        match["code"]
        for concept_block in detailed_matches
        for match in concept_block.get("matches", [])
        if match.get("code")
    }

    return {
        "unique_codes": list(unique_codes),
        "detailed_matches": detailed_matches
    }
