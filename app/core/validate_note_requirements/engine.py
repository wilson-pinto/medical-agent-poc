#app/core/validate_note_requirements/engine.py
import os
import logging
import json
import time
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
    print("Gemini Model configured successfully.")
else:
    GEMINI_MODEL = None
    print("GEMINI_API_KEY not found. Gemini will not be used.")


def _simple_term_check(soap: str, required_terms: List[str]) -> List[str]:
    """Return terms missing from the SOAP text."""
    s = soap.lower()
    return [term for term in required_terms if term.lower() not in s]


def _call_gemini_with_retry(prompt: str, retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
    """Call Gemini with retry logic and always return a dict."""
    if GEMINI_MODEL is None:
        raise RuntimeError("Gemini not configured.")

    text = ""
    for attempt in range(1, retries + 1):
        try:
            resp = GEMINI_MODEL.generate_content(prompt)
            text = getattr(resp, "text", "").strip()
            if text.startswith("```"):
                text = text.strip("` \n")
            data = json.loads(text)
            if not isinstance(data.get("suggestions"), list):
                data["suggestions"] = []
            return data
        except Exception as e:
            logger.warning("Gemini attempt %d/%d failed: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(delay)
            else:
                import re
                try:
                    m = re.search(r'(\{.*\})', text, flags=re.DOTALL)
                    if m:
                        data = json.loads(m.group(1))
                        if not isinstance(data.get("suggestions"), list):
                            data["suggestions"] = []
                        return data
                except Exception:
                    logger.exception("Gemini returned non-JSON response on final retry.")
                return {"suggestions": []}


def validate_soap_against_rules(soap: str, service_codes: List[str]) -> List[dict]:
    """Validate SOAP note against HELFO service codes, return list of dicts."""
    rules = load_rules()
    results: List[PerCodeResult] = []

    for code in service_codes:
        code_key = str(code).strip()
        rule = rules.get(code_key)

        if rule is None:
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
        missing_terms_simple = _simple_term_check(soap, required_terms)
        compliance_simple = "fail" if missing_terms_simple else "pass"

        missing_terms = missing_terms_simple
        compliance = compliance_simple
        suggestions = rule.get("suggestions") or []
        gemini_used = False
        gemini_reasoning = None

        if USE_GEMINI and GEMINI_MODEL:
            try:
                prompt = build_gemini_prompt(code_key, rule.get("requirement", ""), soap)
                resp = _call_gemini_with_retry(prompt)

                gemini_used = True
                gemini_reasoning = json.dumps(resp)

                status = resp.get("status", "").lower()
                if status in ["pass", "warn", "fail"]:
                    compliance = status

                if isinstance(resp.get("missing_terms"), list):
                    missing_terms = resp["missing_terms"]

                suggestions = resp.get("suggestions") or suggestions

            except Exception as e:
                logger.error("Gemini validation failed. Falling back to simple check.", exc_info=True)
                gemini_used = True
                gemini_reasoning = json.dumps({
                    "error": str(e),
                    "fallback_to": "simple_term_check"
                })

        result = PerCodeResult(
            service_code=code_key,
            compliance=compliance,
            missing_terms=missing_terms,
            suggestions=suggestions,
            gemini_used=gemini_used,
            gemini_reasoning=gemini_reasoning,
            rule_version=rule.get("version")
        )

        results.append(result)

    return [r.dict() for r in results]
