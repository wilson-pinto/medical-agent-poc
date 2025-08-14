# app/core/rerank_gemini.py
from typing import List, Dict
import google.generativeai as genai
from app.config import GEMINI_API_KEY

# Configure Gemini model if API key is provided
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

def rerank_gemini(soap_text: str, candidates: List[Dict]) -> Dict:
    """
    Selects the best service code from candidates using Gemini.
    Always returns a dict with at least 'code', 'description', and 'reasoning'.
    """
    # Handle empty candidate list
    if not candidates:
        return {
            "code": "UNKNOWN",
            "description": "No candidates available",
            "reasoning": "No candidates found from semantic search"
        }

    # Fallback if Gemini model not configured
    if not model:
        first = candidates[0]
        return {
            "code": first.get("code", "UNKNOWN"),
            "description": first.get("description", ""),
            "reasoning": "Gemini not configured, returning first candidate"
        }

    # Prepare candidate codes for prompt
    candidate_codes = [c.get("code", "UNKNOWN") for c in candidates]

    prompt = f"""You are a medical billing assistant.
A user entered the SOAP note: \"{soap_text}\"

Select the most appropriate service code from the list below:
"""
    for i, code in enumerate(candidate_codes, 1):
        prompt += f"{i}. {code}\n"

    prompt += """
Respond with only the code ID and a short reasoning.
Example: MT001 - This matches spine therapy.
"""

    # Call Gemini safely
    try:
        response = model.generate_content(prompt)
        selected_text = response.text.strip()
        selected_code = selected_text.split(" ")[0] if selected_text else candidate_codes[0]
    except Exception as e:
        selected_code = candidate_codes[0]
        selected_text = f"Gemini call failed: {e}. Using fallback candidate."

    # Match selected code to candidate dict
    selected_candidate = next((c for c in candidates if c.get("code") == selected_code), None)
    if not selected_candidate:
        # Fallback if Gemini returned invalid code
        selected_candidate = candidates[0]
        selected_text += " | Fallback to first candidate"

    return {
        "code": selected_candidate.get("code", "UNKNOWN"),
        "description": selected_candidate.get("description", ""),
        "reasoning": selected_text
    }
