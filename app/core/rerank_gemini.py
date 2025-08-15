# # # app/core/rerank_gemini.py
# # from typing import List, Dict
# # import google.generativeai as genai
# # from app.config import GEMINI_API_KEY
# #
# # # Configure Gemini model if API key is provided
# # if GEMINI_API_KEY:
# #     genai.configure(api_key=GEMINI_API_KEY)
# #     model = genai.GenerativeModel("gemini-1.5-flash")
# # else:
# #     model = None
# #
# # def rerank_gemini(soap_text: str, candidates: List[Dict]) -> Dict:
# #     """
# #     Selects the best service code from candidates using Gemini.
# #     Always returns a dict with at least 'code', 'description', and 'reasoning'.
# #     """
# #     # Handle empty candidate list
# #     if not candidates:
# #         return {
# #             "code": "UNKNOWN",
# #             "description": "No candidates available",
# #             "reasoning": "No candidates found from semantic search"
# #         }
# #
# #     # Fallback if Gemini model not configured
# #     if not model:
# #         first = candidates[0]
# #         return {
# #             "code": first.get("code", "UNKNOWN"),
# #             "description": first.get("description", ""),
# #             "reasoning": "Gemini not configured, returning first candidate"
# #         }
# #
# #     # Prepare candidate codes for prompt
# #     candidate_codes = [c.get("code", "UNKNOWN") for c in candidates]
# #
# #     prompt = f"""You are a medical billing assistant.
# # A user entered the SOAP note: \"{soap_text}\"
# #
# # Select the most appropriate service code from the list below:
# # """
# #     for i, code in enumerate(candidate_codes, 1):
# #         prompt += f"{i}. {code}\n"
# #
# #     prompt += """
# # Respond with only the code ID and a short reasoning.
# # Example: MT001 - This matches spine therapy.
# # """
# #
# #     # Call Gemini safely
# #     try:
# #         response = model.generate_content(prompt)
# #         selected_text = response.text.strip()
# #         selected_code = selected_text.split(" ")[0] if selected_text else candidate_codes[0]
# #     except Exception as e:
# #         selected_code = candidate_codes[0]
# #         selected_text = f"Gemini call failed: {e}. Using fallback candidate."
# #
# #     # Match selected code to candidate dict
# #     selected_candidate = next((c for c in candidates if c.get("code") == selected_code), None)
# #     if not selected_candidate:
# #         # Fallback if Gemini returned invalid code
# #         selected_candidate = candidates[0]
# #         selected_text += " | Fallback to first candidate"
# #
# #     return {
# #         "code": selected_candidate.get("code", "UNKNOWN"),
# #         "description": selected_candidate.get("description", ""),
# #         "reasoning": selected_text
# #     }
# # app/core/rerank_gemini.py
# from typing import List, Dict
# import google.generativeai as genai
# from app.config import GEMINI_API_KEY
# from app.utils.gemini_fallback_logic import get_service_code_fallback
#
# # Configure Gemini model if API key is provided
# if GEMINI_API_KEY:
#     genai.configure(api_key=GEMINI_API_KEY)
#     model = genai.GenerativeModel("gemini-1.5-flash")
# else:
#     model = None
#
# def rerank_gemini(soap_text: str, candidates: List[Dict]) -> Dict:
#     """
#     Selects the best service code from candidates using Gemini.
#     Always returns a dict with at least 'code', 'description', and 'reasoning'.
#     Uses a keyword-based fallback if Gemini is unavailable or fails.
#     """
#     # Handle empty candidate list first, as the fallback won't work without a note.
#     if not candidates:
#         return {
#             "code": "UNKNOWN",
#             "description": "No candidates available",
#             "reasoning": "No candidates found from semantic search"
#         }
#
#     # Prepare candidate codes for prompt
#     candidate_codes = [c.get("code", "UNKNOWN") for c in candidates]
#
#     # Use the fallback logic if the Gemini model is not configured.
#     if not model:
#         fallback_code, status = get_service_code_fallback(soap_text)
#         fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
#         return {
#             "code": fallback_code,
#             "description": fallback_desc,
#             "reasoning": status
#         }
#
#     prompt = f"""You are a medical billing assistant.
# A user entered the SOAP note: \"{soap_text}\"
#
# Select the most appropriate service code from the list below:
# """
#     for i, code in enumerate(candidate_codes, 1):
#         prompt += f"{i}. {code}\n"
#
#     prompt += """
# Respond with only the code ID and a short reasoning.
# Example: MT001 - This matches spine therapy.
# """
#
#     # Call Gemini, with the new fallback logic in the `except` block.
#     try:
#         response = model.generate_content(prompt)
#         selected_text = response.text.strip()
#         selected_code = selected_text.split(" ")[0] if selected_text else candidate_codes[0]
#
#     except Exception as e:
#         # If Gemini call fails, use the keyword-based fallback.
#         print(f"Gemini call failed during reranking: {e}. Using keyword-based fallback.")
#         fallback_code, status = get_service_code_fallback(soap_text)
#         fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
#         return {
#             "code": fallback_code,
#             "description": fallback_desc,
#             "reasoning": f"Gemini call failed. {status}"
#         }
#
#     # Match selected code to candidate dict
#     selected_candidate = next((c for c in candidates if c.get("code") == selected_code), None)
#     if not selected_candidate:
#         # Fallback if Gemini returned an invalid code (should be rare)
#         fallback_code, status = get_service_code_fallback(soap_text)
#         fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
#         return {
#             "code": fallback_code,
#             "description": fallback_desc,
#             "reasoning": f"Gemini returned an invalid code. {status}"
#         }
#
#     return {
#         "code": selected_candidate.get("code", "UNKNOWN"),
#         "description": selected_candidate.get("description", ""),
#         "reasoning": selected_text
#     }
# app/core/rerank_gemini.py
# from typing import List, Dict, Any
# import google.generativeai as genai
# from app.config import GEMINI_API_KEY
# from app.utils.gemini_fallback_logic import get_service_code_fallback
#
# # ------------------------------------------------
# # Initialization and Configuration
# # ------------------------------------------------
# # Configure the Gemini model for API calls if a key is available.
# # The 'gemini-1.5-flash' model is a good choice for its speed and cost-effectiveness.
# if GEMINI_API_KEY:
#     genai.configure(api_key=GEMINI_API_KEY)
#     model = genai.GenerativeModel("gemini-1.5-flash")
# else:
#     # If no API key, the model will remain None, triggering the fallback logic.
#     model = None
#
# # ------------------------------------------------
# # Main Reranking Function
# # ------------------------------------------------
# def rerank_gemini(soap_text: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """
#     Selects the best service code from a list of candidates by using the Gemini model.
#     This function includes a robust fallback mechanism if the Gemini model is
#     not configured or if the API call fails.
#
#     Args:
#         soap_text: The full SOAP note text provided by the user.
#         candidates: A list of candidate service codes, each as a dictionary
#                     with at least 'code' and 'description'.
#
#     Returns:
#         A dictionary representing the best-matched service code, including its
#         'code', 'description', and the 'reasoning' for its selection.
#     """
#     # 1. Handle edge case: no candidates found from the initial search.
#     if not candidates:
#         return {
#             "code": "UNKNOWN",
#             "description": "No candidates available",
#             "reasoning": "No candidates found from semantic search."
#         }
#
#     # 2. Prepare the prompt for Gemini.
#     # The prompt asks Gemini to act as a medical billing assistant to choose
#     # the best code from a list, given the SOAP note.
#     candidate_codes = [c.get("code", "UNKNOWN") for c in candidates]
#     prompt = f"""You are a medical billing assistant.
# A user entered the SOAP note: \"{soap_text}\"
#
# Select the most appropriate service code from the list below:
# """
#     for i, code in enumerate(candidate_codes, 1):
#         prompt += f"{i}. {code}\n"
#
#     prompt += """
# Respond with only the code ID and a short reasoning.
# Example: MT001 - This matches spine therapy.
# """
#
#     # 3. Handle cases where the Gemini model is not configured or the API call fails.
#     if not model:
#         # Use a keyword-based fallback to select a code if Gemini is not available.
#         fallback_code, status = get_service_code_fallback(soap_text)
#         fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
#         return {
#             "code": fallback_code,
#             "description": fallback_desc,
#             "reasoning": status
#         }
#
#     try:
#         # Make the API call to Gemini.
#         response = model.generate_content(prompt)
#         selected_text = response.text.strip()
#
#         # Parse the response to get the selected code.
#         selected_code = selected_text.split(" ")[0] if selected_text else candidate_codes[0]
#
#     except Exception as e:
#         # If the API call fails, use the keyword-based fallback logic.
#         print(f"Gemini call failed during reranking: {e}. Using keyword-based fallback.")
#         fallback_code, status = get_service_code_fallback(soap_text)
#         fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
#         return {
#             "code": fallback_code,
#             "description": fallback_desc,
#             "reasoning": f"Gemini call failed. {status}"
#         }
#
#     # 4. Find the selected candidate's full information from the original list.
#     selected_candidate = next((c for c in candidates if c.get("code") == selected_code), None)
#
#     # 5. Handle cases where Gemini returns an invalid code that is not in the candidate list.
#     if not selected_candidate:
#         # This is a final safety net. Use the keyword-based fallback.
#         fallback_code, status = get_service_code_fallback(soap_text)
#         fallback_desc = next((c.get('description') for c in candidates if c.get('code') == fallback_code), "N/A")
#         return {
#             "code": fallback_code,
#             "description": fallback_desc,
#             "reasoning": f"Gemini returned an invalid code. {status}"
#         }
#
#     # 6. Return the final, selected candidate with its reasoning.
#     return {
#         "code": selected_candidate.get("code", "UNKNOWN"),
#         "description": selected_candidate.get("description", ""),
#         "reasoning": selected_text
#     }
#c1
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
