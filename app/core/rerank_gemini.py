
from typing import List, Dict, Any
import google.generativeai as genai
from app.config import GEMINI_API_KEY
from app.utils.gemini_fallback_logic import get_service_code_fallback

# ------------------------------------------------
# Initialization and Configuration
# ------------------------------------------------
# Configure the Gemini model for API calls if a key is available.
# The 'gemini-1.5-flash' model is a good choice for its speed and cost-effectiveness.
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    # If no API key, the model will remain None, triggering the fallback logic.
    model = None

# ------------------------------------------------
# Main Reranking Function
# ------------------------------------------------
def rerank_gemini(soap_text: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Selects the best service code from a list of candidates by using the Gemini model.
    This function includes a robust fallback mechanism if the Gemini model is
    not configured or if the API call fails.

    Args:
        soap_text: The full SOAP note text provided by the user.
        candidates: A list of candidate service codes, each as a dictionary
                    with at least 'code' and 'description'.

    Returns:
        A dictionary representing the best-matched service code, including its
        'code', 'description', and the 'reasoning' for its selection.
    """
    # 1. Handle edge case: no candidates found from the initial search.
    # This scenario would also trigger a fallback to '99215' inside the fallback
    # function itself, but it's good practice to handle it here explicitly.
    if not candidates:
        fallback_code, status = get_service_code_fallback(soap_text, candidates)
        return {
            "code": fallback_code,
            "description": "No candidates available",
            "reasoning": status
        }

    # 2. Handle cases where the Gemini model is not configured.
    if not model:
        print("Gemini model not configured. Using fallback logic.")
        fallback_code, status = get_service_code_fallback(soap_text, candidates)
        fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
        return {
            "code": fallback_code,
            "description": fallback_desc,
            "reasoning": status
        }

    # 3. Prepare the prompt for Gemini.
    candidate_codes = [c.get("code", "UNKNOWN") for c in candidates]
    prompt = f"""You are a medical billing assistant.
A user entered the SOAP note: "{soap_text}"

Select the most appropriate service code from the list below:
"""
    for i, code in enumerate(candidate_codes, 1):
        prompt += f"{i}. {code}\n"

    prompt += """
Respond with only the code ID and a short reasoning.
Example: MT001 - This matches spine therapy.
"""
    try:
        # Make the API call to Gemini.
        response = model.generate_content(prompt)
        selected_text = response.text.strip()

        # Parse the response to get the selected code.
        # This handles cases where the response is formatted as 'CODE - Reason'
        selected_code = selected_text.split(" ")[0] if selected_text else None

    except Exception as e:
        # If the API call fails, use the fallback logic with the original candidates.
        print(f"Gemini call failed during reranking: {e}. Using fallback logic.")
        fallback_code, status = get_service_code_fallback(soap_text, candidates)
        fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
        return {
            "code": fallback_code,
            "description": fallback_desc,
            "reasoning": f"Gemini call failed. {status}"
        }

    # 4. Find the selected candidate's full information from the original list.
    selected_candidate = next((c for c in candidates if c.get("code") == selected_code), None)

    # 5. Handle cases where Gemini returns an invalid code that is not in the candidate list.
    if not selected_candidate:
        # This is the final safety net. Use the fallback logic with the original candidates.
        print("Gemini returned an invalid code. Using fallback logic.")
        fallback_code, status = get_service_code_fallback(soap_text, candidates)
        fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
        return {
            "code": fallback_code,
            "description": fallback_desc,
            "reasoning": f"Gemini returned an invalid code. {status}"
        }

    # 6. Return the final, selected candidate with its reasoning.
    return {
        "code": selected_candidate.get("code", "UNKNOWN"),
        "description": selected_candidate.get("description", ""),
        "reasoning": selected_text
    }
