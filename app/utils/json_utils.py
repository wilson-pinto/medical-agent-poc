import re
import json

def safe_extract_json(text: str):
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
        return json.loads(cleaned)
    except Exception:
        return [{"error": "Invalid JSON", "raw": text}]

def clean_model_text(text: str) -> str:
    """
    Remove markdown/json fences and surrounding whitespace.
    """
    if text is None:
        return ""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return cleaned.strip()