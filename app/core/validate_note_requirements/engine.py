# app/core/validate_note_requirements/engine.py
import os
import logging
import google.generativeai as genai
from typing import List, Dict, Any
from app.core.validate_note_requirements.rules_loader import load_rules
from app.core.validate_note_requirements.prompts import build_gemini_prompt
from app.schemas_new.validate_note_requirements import PerCodeResult
from app.utils.json_utils import safe_extract_json, clean_model_text

logger = logging.getLogger(__name__)

USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if USE_GEMINI and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
else:
    GEMINI_MODEL = None

def _simple_term_check(soap: str, required_terms: List[str]) -> List[str]:
    """Return list of terms that are missing (case-insensitive)."""
    missing = []
    s = soap.lower()
    for term in required_terms:
        if term.lower() not in s:
            missing.append(term)
    return missing

def _call_gemini(prompt: str, timeout_s: int = 6) -> Dict[str, Any]:
    """Call Gemini (safely) and parse JSON. Returns dict or raises."""
    if GEMINI_MODEL is None:
        raise RuntimeError("Gemini not available/configured.")
    resp = GEMINI_MODEL.generate_content(prompt)
    text = clean_model_text(resp.text)
    return safe_extract_json(text) 

def validate_soap_against_codes(soap: str, service_codes: List[str]) -> Dict[str, Any]:
    """Main function. Returns structure matching CheckNoteResponse."""
    rules = load_rules()
    results = []
    for code in service_codes:
        code_key = str(code).strip()
        rule = rules.get(code_key)
        if not rule:
            r = PerCodeResult(
                service_code=code_key,
                compliance="unknown",
                missing_terms=[],
                suggestions=None,
                gemini_used=False,
                gemini_reasoning=None,
                rule_version=None
            )
            results.append(r)
            continue

        required_terms = rule.get("required_terms", [])
        missing_terms = _simple_term_check(soap, required_terms)

        # Default assumption before Gemini
        compliance = "fail"
        gemini_used = False
        gemini_reasoning = None

        # If nothing missing → deterministic pass
        if not missing_terms:
            compliance = "pass"
        elif USE_GEMINI and GEMINI_MODEL:
            try:
                prompt = build_gemini_prompt(code_key, rule.get("requirement", ""), soap)
                resp = _call_gemini(prompt)
                gemini_used = True
                gemini_reasoning = resp['explanation']
                # gemini_reasoning = json.dumps(resp)

                # Expect: {"status": "pass"|"warn"|"fail", ...}
                status = resp.get("status", "").lower()
                if status in ["pass", "warn", "fail"]:
                    compliance = status
                else:
                    # fallback: treat "pass" bool if older prompt format
                    compliance = "pass" if resp.get("pass") else "fail"

                # Sync missing terms if model provided them
                if isinstance(resp.get("missing_terms"), list):
                    missing_terms = resp["missing_terms"]

            except Exception:
                logger.exception("Gemini call failed; using deterministic result.")
                compliance = "fail"

        r = PerCodeResult(
            service_code=code_key,
            compliance=compliance,
            missing_terms=missing_terms,
            suggestions=rule.get("suggestions", []),
            gemini_used=gemini_used,
            gemini_reasoning=gemini_reasoning,
            rule_version=rule.get("version")
        )
        results.append(r)

    # Overall status
    statuses = [r.compliance for r in results]
    if all(s == "pass" for s in statuses):
        overall = "pass"
    elif any(s == "pass" for s in statuses) or any(s == "warn" for s in statuses):
        overall = "partial"
    elif all(s == "unknown" for s in statuses):
        overall = "unknown"
    else:
        overall = "fail"

    return {"overall": overall, "results": results}
