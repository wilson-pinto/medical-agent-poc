# app/core/validate_note_requirements/prompts.py
def build_gemini_prompt(service_code: str, rule_text: str, soap_note: str) -> str:
    return f"""
You are an expert HELFO claim reviewer for Norwegian healthcare billing codes.

Task:
1. Read the service code: "{service_code}" and its documentation requirement: "{rule_text}".
2. Read the SOAP note: "{soap_note}".
3. Decide if the SOAP note documentation justifies billing this service code according to the HELFO rules provided.

Classification rules:
- "pass": Fully meets all documentation requirements — all required terms, details, and context are clearly present.
- "warn": Partially meets requirements — some details are missing, ambiguous, vague, or implied but not explicitly stated. Use this if the note could be interpreted as compliant but is not clearly complete.
- "fail": Does not meet requirements — key documentation is missing or the context clearly contradicts the requirement.

Output format:
Return ONLY a valid JSON object:
{{
  "status": "pass" | "warn" | "fail",
  "explanation": "<short explanation in English or Norwegian>",
  "missing_terms": ["<term1>", "<term2>", ...]
}}

Additional rules:
- "missing_terms" should list only the most critical missing or unclear words/phrases from the HELFO requirement.
- If nothing is missing, return an empty list.
- Do NOT include any text outside the JSON object.
"""
