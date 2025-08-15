# app/utils/gemini_fallback_logic.py
def get_service_code_fallback(soap_note: str, top_service_codes: list = None) -> tuple:
    """
    Provides a simple fallback for service code prediction by returning the
    top candidate from the initial semantic search.

    This function is intended to be called if the primary API-based prediction
    fails. It relies on the pre-sorted list of candidates provided.

    Args:
        soap_note (str): The complete SOAP note from the patient visit.
        top_service_codes (list): A list of top service code candidates,
                                   ranked by a semantic search. Each candidate
                                   is a dictionary.

    Returns:
        tuple: A tuple containing the predicted service code (str) and a
               status message (str) indicating it was a fallback.
    """
    # Check if a list of top service codes was provided and is not empty.
    if top_service_codes and len(top_service_codes) > 0:
        # Return the code of the very first candidate, which is the
        # best match from the initial semantic search.
        first_candidate = top_service_codes[0]
        code = first_candidate.get("code", "UNKNOWN")
        return code, "Fallback: Using top candidate from semantic search."

    # If no top codes were provided or the list was empty, return a default code.
    return '99215', "Fallback: No candidate codes available. Returning default code."

# --- Example Usage ---

if __name__ == "__main__":
    # Example 1: Successful fallback with a candidate list
    soap_note_1 = """
    S: Patient presents for a routine follow-up visit. No new complaints.
    O: Vitals stable.
    A: Follow-up complete.
    P: Continue current medication regimen.
    """
    candidate_list = [
        {"code": "99213", "description": "Follow-up visit", "similarity": 0.85},
        {"code": "99214", "description": "Extended visit", "similarity": 0.70}
    ]
    code, status = get_service_code_fallback(soap_note_1, candidate_list)
    print(f"Predicted Code: {code}")
    print(f"Status: {status}")

    print("-" * 20)

    # Example 2: Fallback with an empty list
    soap_note_2 = "Patient has a headache."
    empty_list = []
    code, status = get_service_code_fallback(soap_note_2, empty_list)
    print(f"Predicted Code: {code}")
    print(f"Status: {status}")
