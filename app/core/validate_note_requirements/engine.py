# #app/core/validate_note_requirements/engine.py
# import os
# import logging
# import json
# import time
# from typing import List, Dict, Any
# from app.core.validate_note_requirements.rules_loader import load_rules
# from app.core.validate_note_requirements.prompts import build_gemini_prompt
# from app.schemas_new.validate_note_requirements import PerCodeResult
#
# import google.generativeai as genai
#
# logger = logging.getLogger(__name__)
#
# USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() == "true"
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#
# if USE_GEMINI and GEMINI_API_KEY:
#     genai.configure(api_key=GEMINI_API_KEY)
#     GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
# else:
#     GEMINI_MODEL = None
#
#
# def _simple_term_check(soap: str, required_terms: List[str]) -> List[str]:
#     """Return terms missing from the SOAP text."""
#     s = soap.lower()
#     return [term for term in required_terms if term.lower() not in s]
#
#
# def _call_gemini_with_retry(prompt: str, retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
#     """Call Gemini with retry logic and always return a dict."""
#     if GEMINI_MODEL is None:
#         raise RuntimeError("Gemini not configured.")
#
#     text = ""  # ✅ Initialize to avoid UnboundLocalError
#
#     for attempt in range(1, retries + 1):
#         try:
#             resp = GEMINI_MODEL.generate_content(prompt)
#             text = getattr(resp, "text", "").strip()
#             if text.startswith("```"):
#                 text = text.strip("` \n")
#             data = json.loads(text)
#             if not isinstance(data.get("suggestions"), list):
#                 data["suggestions"] = []
#             return data
#         except Exception as e:
#             logger.warning("Gemini attempt %d/%d failed: %s", attempt, retries, e)
#             if attempt < retries:
#                 time.sleep(delay)
#             else:
#                 # Final fallback parsing
#                 import re
#                 try:
#                     m = re.search(r'(\{.*\})', text, flags=re.DOTALL)
#                     if m:
#                         data = json.loads(m.group(1))
#                         if not isinstance(data.get("suggestions"), list):
#                             data["suggestions"] = []
#                         return data
#                 except Exception:
#                     logger.exception("Gemini returned non-JSON response on final retry.")
#                 return {"suggestions": []}  # ✅ Always return a dict
#
#
# def validate_soap_against_rules(soap: str, service_codes: List[str]) -> List[dict]:
#     """Validate SOAP note against HELFO service codes, return list of dicts."""
#     rules = load_rules()
#     results: List[PerCodeResult] = []
#
#     for code in service_codes:
#         code_key = str(code).strip()
#         rule = rules.get(code_key)
#
#         if not rule:
#             results.append(
#                 PerCodeResult(
#                     service_code=code_key,
#                     compliance="unknown",
#                     missing_terms=[],
#                     suggestions=[],
#                     gemini_used=False,
#                     gemini_reasoning=None,
#                     rule_version=None
#                 )
#             )
#             continue
#
#         required_terms = rule.get("required_terms", [])
#         missing_terms = _simple_term_check(soap, required_terms)
#
#         compliance = "fail" if missing_terms else "pass"
#         gemini_used = False
#         gemini_reasoning = None
#         suggestions = rule.get("suggestions") or []
#
#         if missing_terms and USE_GEMINI and GEMINI_MODEL:
#             try:
#                 prompt = build_gemini_prompt(code_key, rule.get("requirement", ""), soap)
#                 resp = _call_gemini_with_retry(prompt)
#                 gemini_used = True
#                 gemini_reasoning = json.dumps(resp)
#
#                 status = resp.get("status", "").lower()
#                 if status in ["pass", "warn", "fail"]:
#                     compliance = status
#                 else:
#                     compliance = "pass" if resp.get("pass") else "fail"
#
#                 if isinstance(resp.get("missing_terms"), list):
#                     missing_terms = resp["missing_terms"]
#
#                 suggestions = resp.get("suggestions") or suggestions
#
#             except Exception as e:
#                 logger.exception("Gemini final fallback failed.")
#                 compliance = "fail"
#                 gemini_reasoning = json.dumps({"error": str(e)})
#                 suggestions = rule.get("suggestions") or []
#
#         results.append(
#             PerCodeResult(
#                 service_code=code_key,
#                 compliance=compliance,
#                 missing_terms=missing_terms,
#                 suggestions=suggestions,
#                 gemini_used=gemini_used,
#                 gemini_reasoning=gemini_reasoning,
#                 rule_version=rule.get("version")
#             )
#         )
#
#     return [r.dict() for r in results]
#justchanged
# app/core/validate_note_requirements/engine.py
# import os
# import logging
# import json
# import time
# from typing import List, Dict, Any
# from app.core.validate_note_requirements.rules_loader import load_rules
# from app.core.validate_note_requirements.prompts import build_gemini_prompt
# from app.schemas_new.validate_note_requirements import PerCodeResult
#
# import google.generativeai as genai
#
# logger = logging.getLogger(__name__)
#
# USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() == "true"
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#
# if USE_GEMINI and GEMINI_API_KEY:
#     genai.configure(api_key=GEMINI_API_KEY)
#     GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
# else:
#     GEMINI_MODEL = None
#
#
# def _simple_term_check(soap: str, required_terms: List[str]) -> List[str]:
#     """Return terms missing from the SOAP text."""
#     s = soap.lower()
#     return [term for term in required_terms if term.lower() not in s]
#
#
# def _call_gemini_with_retry(prompt: str, retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
#     """Call Gemini with retry logic and always return a dict."""
#     if GEMINI_MODEL is None:
#         raise RuntimeError("Gemini not configured.")
#
#     text = ""  # Initialize to avoid UnboundLocalError
#
#     for attempt in range(1, retries + 1):
#         try:
#             resp = GEMINI_MODEL.generate_content(prompt)
#             text = getattr(resp, "text", "").strip()
#             if text.startswith("```"):
#                 text = text.strip("` \n")
#             data = json.loads(text)
#             if not isinstance(data.get("suggestions"), list):
#                 data["suggestions"] = []
#             return data
#         except Exception as e:
#             logger.warning("Gemini attempt %d/%d failed: %s", attempt, retries, e)
#             if attempt < retries:
#                 time.sleep(delay)
#             else:
#                 # Final fallback parsing
#                 import re
#                 try:
#                     m = re.search(r'(\{.*\})', text, flags=re.DOTALL)
#                     if m:
#                         data = json.loads(m.group(1))
#                         if not isinstance(data.get("suggestions"), list):
#                             data["suggestions"] = []
#                         return data
#                 except Exception:
#                     logger.exception("Gemini returned non-JSON response on final retry.")
#                 return {"suggestions": []}  # Always return a dict
#
#
# def validate_soap_against_rules(soap: str, service_codes: List[str]) -> List[dict]:
#     """Validate SOAP note against HELFO service codes, return list of dicts."""
#     rules = load_rules()
#     results: List[PerCodeResult] = []
#
#     for code in service_codes:
#         code_key = str(code).strip()
#         rule = rules.get(code_key)
#
#         if not rule:
#             results.append(
#                 PerCodeResult(
#                     service_code=code_key,
#                     compliance="unknown",
#                     missing_terms=[],
#                     suggestions=[],
#                     gemini_used=False,
#                     gemini_reasoning=None,
#                     rule_version=None
#                 )
#             )
#             continue
#
#         # Always perform the simple term check first as a reliable baseline
#         required_terms = rule.get("required_terms", [])
#         missing_terms_simple = _simple_term_check(soap, required_terms)
#         compliance_simple = "fail" if missing_terms_simple else "pass"
#
#         missing_terms = missing_terms_simple
#         compliance = compliance_simple
#         suggestions = rule.get("suggestions") or []
#         gemini_used = False
#         gemini_reasoning = None
#
#         if USE_GEMINI and GEMINI_MODEL:
#             try:
#                 prompt = build_gemini_prompt(code_key, rule.get("requirement", ""), soap)
#                 resp = _call_gemini_with_retry(prompt)
#                 gemini_used = True
#                 gemini_reasoning = json.dumps(resp)
#
#                 status = resp.get("status", "").lower()
#                 if status in ["pass", "warn", "fail"]:
#                     compliance = status
#                 else:
#                     # Fallback to simple check if Gemini's status is invalid
#                     compliance = "pass" if resp.get("pass") else compliance_simple
#
#                 if isinstance(resp.get("missing_terms"), list):
#                     missing_terms = resp["missing_terms"]
#                 else:
#                     # Fallback to simple check's missing terms if Gemini's are invalid
#                     missing_terms = missing_terms_simple
#
#                 suggestions = resp.get("suggestions") or suggestions
#
#             except Exception as e:
#                 logger.exception("Gemini validation failed. Falling back to simple term check.")
#                 # The values for missing_terms, compliance, and suggestions already
#                 # hold the results from the simple check, so no change is needed here.
#                 gemini_used = True # Log that we attempted to use it
#                 gemini_reasoning = json.dumps({"error": str(e), "fallback_to": "simple_term_check"})
#
#
#         results.append(
#             PerCodeResult(
#                 service_code=code_key,
#                 compliance=compliance,
#                 missing_terms=missing_terms,
#                 suggestions=suggestions,
#                 gemini_used=gemini_used,
#                 gemini_reasoning=gemini_reasoning,
#                 rule_version=rule.get("version")
#             )
#         )
#
#     return [r.dict() for r in results]
# app/core/validate_note_requirements/engine.py
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
else:
    GEMINI_MODEL = None


def _simple_term_check(soap: str, required_terms: List[str]) -> List[str]:
    """Return terms missing from the SOAP text."""
    s = soap.lower()
    return [term for term in required_terms if term.lower() not in s]


def _call_gemini_with_retry(prompt: str, retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
    """Call Gemini with retry logic and always return a dict."""
    if GEMINI_MODEL is None:
        raise RuntimeError("Gemini not configured.")
    print("_call_gemini_with_retry is called")

    text = ""  # Initialize to avoid UnboundLocalError

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
                # Final fallback parsing
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
                return {"suggestions": []}  # Always return a dict


from typing import List
import json

def validate_soap_against_rules(soap: str, service_codes: List[str]) -> List[dict]:
    """Validate SOAP note against HELFO service codes, return list of dicts."""

    print("🚀 Starting validation of SOAP against rules.")
    rules = load_rules()
    print("✅ Rules successfully loaded.")
    print(f"📦 Loaded rules for {len(rules)} service codes.")
    print(f"📝 Incoming SOAP note:\n{soap}")
    print(f"🔢 Service codes to validate: {service_codes}")

    results: List[PerCodeResult] = []
    print(f"📄 Initialized results list: {results}")

    for code in service_codes:
        code_key = str(code).strip()
        print(f"\n🔍 Validating service code: '{code_key}'")

        rule = rules.get(code_key)

        if rule is None:
            print(f"⚠️ No rule found for service code '{code_key}'. Marking as 'unknown'.")
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

        print(f"📏 Rule found for '{code_key}': {rule}")
        required_terms = rule.get("required_terms", [])
        print(f"🧾 Required terms: {required_terms}")

        print(f"🔎 Performing simple term check on SOAP...")
        missing_terms_simple = _simple_term_check(soap, required_terms)
        print(f"❌ Missing terms (simple check): {missing_terms_simple}")
        compliance_simple = "fail" if missing_terms_simple else "pass"
        print(f"📊 Compliance (simple check): {compliance_simple}")

        # Default values (can be overwritten by Gemini)
        missing_terms = missing_terms_simple
        compliance = compliance_simple
        suggestions = rule.get("suggestions") or []
        gemini_used = False
        gemini_reasoning = None

        print(f"🧠 USE_GEMINI = {USE_GEMINI}, GEMINI_MODEL = {GEMINI_MODEL}")
        if USE_GEMINI and GEMINI_MODEL:
            print("🤖 Running Gemini LLM check...")
            try:
                prompt = build_gemini_prompt(code_key, rule.get("requirement", ""), soap)
                print(f"📨 Gemini prompt:\n{prompt}")
                resp = _call_gemini_with_retry(prompt)
                print(f"✅ Gemini response: {resp}")

                gemini_used = True
                gemini_reasoning = json.dumps(resp)

                # Update compliance from Gemini if valid
                status = resp.get("status", "").lower()
                if status in ["pass", "warn", "fail"]:
                    compliance = status
                    print(f"📊 Gemini status override: {compliance}")
                else:
                    print(f"⚠️ Invalid Gemini status '{status}', falling back to simple compliance.")

                # Handle missing terms
                if isinstance(resp.get("missing_terms"), list):
                    missing_terms = resp["missing_terms"]
                    print(f"🧩 Gemini missing terms: {missing_terms}")
                else:
                    print(f"⚠️ Invalid missing_terms format from Gemini, using simple check results.")

                # Update suggestions if provided
                suggestions = resp.get("suggestions") or suggestions
                print(f"💡 Suggestions from Gemini: {suggestions}")

            except Exception as e:
                print("🔥 Gemini validation failed. Falling back to simple check.")
                print(f"🛠️ Error: {e}")
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

        print(f"📥 Appending result for '{code_key}': {result}")
        results.append(result)

    print("\n✅ All service codes processed.")
    print(f"📦 Final results:\n{[r.dict() for r in results]}")

    return [r.dict() for r in results]
