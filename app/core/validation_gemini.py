import re
import json
import google.generativeai as genai
from app.config import GEMINI_API_KEY
from app.utils.json_utils import safe_extract_json
from app.core.diagnosis_search import search_diagnosis, get_diagnosis_descriptions
from app.core.service_search import get_service_code_descriptions

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
    simplify_prompt = f"""
You are a clinical assistant working in a Norwegian EHR system.

Your job is to simplify and summarize the following SOAP note to make it concise and easy to understand, while preserving all relevant medical details.

SOAP Note:
{soap}

Simplified SOAP Note:
"""
    simplify_response = model.generate_content(simplify_prompt)
    simplified_soap = simplify_response.text.strip()
    print("Simplified SOAP Note:", simplified_soap)

    top_diagnoses = search_diagnosis(simplified_soap, top_k=5)  # Assuming this returns a list of top 5 codes
    print("Candidate diagnoses:", top_diagnoses)

    final_prompt = f"""
You are a clinical coding assistant working in a Norwegian EHR system.

Your job is to read the SOAP note and select the most likely ICD-10 or ICPC diagnosis codes from the provided list that match the patient's condition.

SOAP Note:
{soap}

Candidate Diagnosis Codes:
{', '.join(top_diagnoses)}

Respond with a JSON array of codes. Example:
["J02", "R50"]
"""
    response = model.generate_content(final_prompt)
    raw_text = response.text.strip()
    match = re.search(r"\[[^\[\]]+\]", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    else:
        return []

def check_service_diagnosis(soap: str, diagnoses: list[str], service_codes: list[str]) -> dict:
    print("\n=== Starting SOAP check process ===")
    print(f"Original SOAP note:\n{soap}\n")

    # --- STEP 1: Simplify SOAP ---
    simplify_prompt = f"""
You are a clinical assistant working in a Norwegian EHR system.

Your job is to simplify and summarize the following SOAP note to make it concise and easy to understand,
while preserving all relevant medical details.

SOAP Note:
{soap}

Simplified SOAP Note:
"""
    print("[DEBUG] Sending SOAP note for simplification...")
    simplify_response = model.generate_content(simplify_prompt)
    simplified_soap = simplify_response.text.strip()
    print(f"[RESULT] Simplified SOAP note:\n{simplified_soap}\n")

    # --- STEP 2: Check diagnoses ---
    diagnosis_descriptions = get_diagnosis_descriptions(diagnoses)
    print(f"[DEBUG] Diagnosis descriptions: {diagnosis_descriptions}")

    diagnosis_check_prompt = f"""
You are a clinical coding assistant.

Below is a simplified SOAP note and a list of diagnosis codes with their descriptions.
For each code, state PASS if the diagnosis is supported by the SOAP note, otherwise FAIL and give a brief reason.

SOAP Note:
{simplified_soap}

Diagnosis Codes and Descriptions:
{chr(10).join([f"{code}: {desc}" for code, desc in diagnosis_descriptions.items()])}

Respond only with valid JSON in this format:
[
  {{ "code": "J02", "status": "PASS" }},
  {{ "code": "R50", "status": "FAIL", "reason": "No mention of fever" }}
]
"""
    print("[DEBUG] Sending diagnosis check prompt...")
    diagnosis_response = model.generate_content(diagnosis_check_prompt)
    diagnosis_results = safe_extract_json(diagnosis_response.text.strip())
    print(f"[RESULT] Diagnosis check results:\n{diagnosis_results}\n")

    # Collect valid and failed diagnosis codes for service validation
    valid_diagnoses = [d["code"] for d in diagnosis_results if d.get("status") == "PASS"]
    failed_diagnoses = [d["code"] for d in diagnosis_results if d.get("status") == "FAIL"]
    print(f"[DEBUG] Valid diagnoses found: {valid_diagnoses}")
    print(f"[DEBUG] Failed diagnoses found: {failed_diagnoses}\n")

    # --- STEP 3: Check service codes ---
    service_code_descriptions = get_service_code_descriptions(service_codes)
    service_results = []
    for code, desc in service_code_descriptions.items():
        service_check_prompt = f"""
You are a HELFO claim validation assistant working for GPs in Norway.

Your job is to validate whether the following service code (from the tariff table) is correctly supported by:
1. A valid diagnosis code (provided separately)
2. Justification in the SOAP note (free text)

SOAP Note:
{simplified_soap}

Service Code: {code}
Description: {desc}

Valid Diagnosis Codes: {', '.join(valid_diagnoses) if valid_diagnoses else "None"}
Failed Diagnosis Codes: {', '.join(failed_diagnoses) if failed_diagnoses else "None"}

Return a JSON object in this format:
{{
  "code": "{code}",
  "status": "PASS" or "FAIL",
  "reason": "..."
}}
Only return JSON.
"""
        print(f"[DEBUG] Sending service code validation prompt for {code}...")
        service_response = model.generate_content(service_check_prompt)
        result = safe_extract_json(service_response.text.strip())
        service_results.append(result)
        print(f"[RESULT] Service check result for {code}:\n{result}\n")

    print("=== SOAP check process completed ===\n")
    return {
        "diagnosis_results": diagnosis_results,
        "service_results": service_results
    }

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
