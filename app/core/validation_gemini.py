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
def _clean_model_text(text: str) -> str:
    """
    Remove markdown/json fences and surrounding whitespace.
    """
    if text is None:
        return ""
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
        # Try cleaning trailing commas etc. best-effort, otherwise empty
        try:
            cleaned = re.sub(r",\s*(\]|})", r"\1", fragment)
            return json.loads(cleaned)
        except Exception:
            logger.exception("Failed to json-decode array fragment.")
            return []


# ----------------------------
# New Gemini-based grouping / concept extraction
# ----------------------------
GROUPING_PROMPT_TEMPLATE = """You are a clinical documentation assistant.

Your task is to extract and group semantically related symptoms, findings, or clinical observations from the input clinical text. The text may be in English or Norwegian.

Rules:
- Group only the elements that are part of the same condition or refer to the same clinical concept.
- Do NOT combine unrelated symptoms into a single line.
- Keep all relevant clinical details with the related symptom (e.g., duration, severity, location, triggers).
- Do NOT speculate, interpret, or suggest diagnoses here.
- Output must be in the same language as the input.
- Be concise and avoid repeating the same concept.

Note: This output will be used later to find and rank diagnoses with another AI step.

✳️ Output format:
- Return a JSON array of strings.
- Each element is one grouped clinical concept.
- Numbering or bullets are not required.

SOAP Note:
{soap}
"""

def group_clinical_concepts_with_gemini(soap_text: str) -> list[str]:
    """
    Use Gemini to extract and group clinical concepts from the SOAP note.
    Returns a list of grouped clinical concept strings.
    """
    prompt = GROUPING_PROMPT_TEMPLATE.format(soap=soap_text)
    try:
        response = model.generate_content(prompt)
        logger.debug(f"Gemini grouping response: {response.text}")
        text = _clean_model_text(response.text)
        concepts = _extract_first_json_array(text)
        if not concepts:
            logger.warning("Gemini returned empty or invalid JSON for grouping; falling back to whole SOAP.")
            return [soap_text.strip()]
        return concepts
    except Exception as e:
        logger.exception("Gemini grouping failed, falling back to whole SOAP.")
        return [soap_text.strip()]


# ----------------------------
# Gemini reranking for diagnoses
# ----------------------------
def rerank_diagnoses_with_gemini(grouped_concepts: List[str], search_results: dict, final_top_n: int = 1):
    """
    Use Gemini LLM to rerank and validate diagnoses for each clinical concept.
    Returns updated detailed_matches with filtered and ranked diagnoses limited to final_top_n per concept.
    """
    updated_results = []
    for concept_block in search_results.get("diagnoses", []):
        concept = concept_block["concept"]
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
            logger.debug(f"[DEBUG] Gemini raw response for concept '{concept}': {resp.text}")
            text = _clean_model_text(resp.text)

            try:
                filtered = safe_extract_json(text)
            except Exception:
                logger.warning(f"Failed to parse Gemini response JSON, falling back to original matches for concept: {concept}")
                filtered = matches  # fallback if JSON parsing fails

            # Limit final top N matches here
            filtered = filtered[:final_top_n]

            # Add ranking if missing
            for i, diag in enumerate(filtered):
                diag['rank'] = i + 1

            updated_results.append({
                "concept": concept,
                "matches": filtered
            })
        except Exception as e:
            logger.exception(f"Gemini reranking failed for concept: {concept}")
            # fallback to original matches with limit
            updated_results.append({
                "concept": concept,
                "matches": matches[:final_top_n]
            })
    return updated_results


def extract_diagnoses_from_soap(soap: str, top_k: int = 5, min_similarity: float = 0.6, final_top_n: int = 1):
    """
    Enhanced flow:
    1. Remove PII
    2. Group clinical concepts via Gemini LLM (instead of simple regex splitting)
    3. For each concept, get top_k diagnosis matches with explanations from FAISS
    4. Use Gemini LLM to rerank and filter diagnosis matches, limiting final matches to final_top_n
    5. Return both:
       - unique_codes: deduplicated list of all matched codes
       - detailed_matches: full concept → matches mapping
    """
    # --- Step 0: PII removal ---
    try:
        entities = analyze_text(soap)  # returns analyzer results
        soap_no_pii = anonymize_text(soap, entities)
    except Exception:
        logger.exception("PII removal failed; falling back to original SOAP.")
        soap_no_pii = soap

    # --- Step 1: Group clinical concepts using Gemini ---
    try:
        grouped = group_clinical_concepts_with_gemini(soap_no_pii)
        logger.debug(f"[DEBUG] Gemini grouped clinical concepts ({len(grouped)}): {grouped}")
    except Exception:
        logger.exception("Gemini grouping failed; using whole SOAP as single concept.")
        grouped = [soap_no_pii.strip()]

    # --- Step 2: Search for diagnoses with explanations ---
    try:
        search_results = search_diagnosis_with_explanation(
            grouped_concepts=grouped, top_k=top_k, min_similarity=min_similarity
        )
    except Exception:
        logger.exception("search_diagnosis_with_explanation failed.")
        return {
            "unique_codes": [],
            "detailed_matches": []
        }

    # --- Step 3: Gemini reranking with error handling ---
    try:
        detailed_matches = rerank_diagnoses_with_gemini(grouped, search_results, final_top_n=final_top_n)
    except Exception:
        logger.exception("Gemini reranking failed, using original matches.")
        detailed_matches = search_results.get("diagnoses", [])

    # --- Step 4: Deduplicate codes ---
    unique_codes = set()
    for concept_block in detailed_matches:
        for match in concept_block.get("matches", []):
            if match.get("code"):
                unique_codes.add(match["code"])

    return {
        "unique_codes": list(unique_codes),
        "detailed_matches": detailed_matches
    }
