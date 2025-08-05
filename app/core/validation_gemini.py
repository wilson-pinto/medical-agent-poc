import re
import json
import google.generativeai as genai
from app.config import GEMINI_API_KEY
from app.utils.json_utils import safe_extract_json

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def check_note_requirements(soap: str, service_codes: list[str]) -> list[dict]:
    prompt = f"""
You are a Norwegian medical billing assistant in the PatientSky EHR system.
Your job is to check whether each service code has the required documentation inside the SOAP note.

SOAP Note:
{soap}

Service Codes:
{', '.join(service_codes)}

Respond only with valid JSON (no markdown or explanations), in this format:
[
  {{ "code": "301a", "status": "PASS" }},
  {{ "code": "212b", "status": "FAIL", "reason": "No mention of procedure performed" }}
]
"""
    response = model.generate_content(prompt)
    return safe_extract_json(response.text)

def extract_diagnoses_from_soap(soap: str) -> list[str]:
    prompt = f"""
You are a clinical coding assistant working in a Norwegian EHR system.

Your job is to read the SOAP note and extract the most likely ICD-10 or ICPC diagnosis codes that match the patient's condition.

SOAP Note:
{soap}

Respond with a JSON array of codes. Example:
["J02", "R50"]
"""
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    match = re.search(r"\[[^\[\]]+\]", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    else:
        return []

def check_service_diagnosis(soap: str, diagnoses: list[str], service_codes: list[str]) -> list[dict]:
    prompt = f"""
You are a HELFO claim validation assistant working for GPs in Norway.

Your job is to validate whether each selected service code (from the tariff table) is correctly supported by:
1. A valid diagnosis code (provided separately)
2. Justification in the SOAP note (free text)

SOAP Note:
{soap}

Diagnosis Codes: {', '.join(diagnoses)}
Service Codes: {', '.join(service_codes)}

Return a list in this format:
[
  {{ "code": "K01a", "status": "PASS" }},
  {{ "code": "K01d", "status": "FAIL", "reason": "No eyelid condition mentioned in SOAP" }}
]

Only return JSON — no explanation or extra commentary.
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return [{"error": "Could not parse Gemini response"}]

def check_semantic_combo_warning(service_codes: list[str], soap: str) -> list[str]:
    prompt = f"""
You are a HELFO billing validation assistant in Norway.

Task:
Check whether the combination of the following service codes looks suspicious or unusual. These codes were selected together for a single patient consultation.

Service Codes:
{', '.join(service_codes)}

SOAP Note:
{soap}

If the combination looks unusual or rarely used together, provide a warning and explain briefly.

Return a list of warnings like:
[
  "K01a and 301a are rarely used together unless pre/post-op context is noted.",
  "1ad and 1ae are rarely valid together without emergency justification."
]

If no issues are found, return an empty list: []
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return ["Could not parse Gemini output. Please verify manually."]
