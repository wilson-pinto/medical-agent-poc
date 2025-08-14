import os
import logging
import json
from typing import List, Dict, Any
from app.core.validate_note_requirements.rules_loader import load_rules
from app.core.validate_note_requirements.prompts import build_gemini_prompt
from app.schemas_new.validate_note_requirements import PerCodeResult

import google.generativeai as genai

logger = logging.getLogger(__name__)

USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if USE_GEMINI and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
else:
    GEMINI_MODEL = None

def _simple_term_check(soap: str, required_terms: List[str]) -> List[str]:
    """Return terms missing from the SOAP text."""
    s = soap.lower()
    return [term for term in required_terms if term.lower() not in s]

def _call_gemini(prompt: str) -> Dict[str, Any]:
    """Call Gemini safely and return JSON dict."""
    if GEMINI_MODEL is None:
        raise RuntimeError("Gemini not configured.")
    try:
        resp = GEMINI_MODEL.generate_content(prompt)
        text = resp.text.strip()
        if text.startswith("```"):
            text = text.strip("` \n")
        data = json.loads(text)
        # Ensure suggestions is always a list
        if not isinstance(data.get("suggestions"), list):
            data["suggestions"] = []
        return data
    except Exception:
        import re
        m = re.search(r'(\{.*\})', text, flags=re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                if not isinstance(data.get("suggestions"), list):
                    data["suggestions"] = []
                return data
            except Exception:
                logger.exception("Gemini returned non-JSON response.")
        logger.warning("Gemini response could not be parsed; returning empty dict.")
        return {"suggestions": []}

def validate_soap_against_rules(soap: str, service_codes: List[str]) -> List[dict]:
    """Validate SOAP note against HELFO service codes, return list of dicts."""
    rules = load_rules()
    results: List[PerCodeResult] = []

    for code in service_codes:
        code_key = str(code).strip()
        rule = rules.get(code_key)

        if not rule:
            results.append(
                PerCodeResult(
                    service_code=code_key,
                    compliance="unknown",
                    missing_terms=[],
                    suggestions=[],
                    gemini_used=False,
                    gemini_reasoning=None,
                    rule_version=None
                )
            )
            continue

        required_terms = rule.get("required_terms", [])
        missing_terms = _simple_term_check(soap, required_terms)

        compliance = "fail" if missing_terms else "pass"
        gemini_used = False
        gemini_reasoning = None

        if missing_terms and USE_GEMINI and GEMINI_MODEL:
            try:
                prompt = build_gemini_prompt(code_key, rule.get("requirement", ""), soap)
                resp = _call_gemini(prompt)
                gemini_used = True
                gemini_reasoning = json.dumps(resp)

                # Normalize compliance
                status = resp.get("status", "").lower()
                if status in ["pass", "warn", "fail"]:
                    compliance = status
                else:
                    compliance = "pass" if resp.get("pass") else "fail"

                # Use Gemini's missing_terms if provided
                if isinstance(resp.get("missing_terms"), list):
                    missing_terms = resp["missing_terms"]

                # Ensure suggestions is always a list
                suggestions = resp.get("suggestions") or []
            except Exception:
                logger.exception("Gemini call failed; using deterministic result.")
                compliance = "fail"
                suggestions = rule.get("suggestions") or []
        else:
            suggestions = rule.get("suggestions") or []

        results.append(
            PerCodeResult(
                service_code=code_key,
                compliance=compliance,
                missing_terms=missing_terms,
                suggestions=suggestions,
                gemini_used=gemini_used,
                gemini_reasoning=gemini_reasoning,
                rule_version=rule.get("version")
            )
        )

    # Convert Pydantic objects to dicts for nodes
    return [r.dict() for r in results]
