import re
import json

def safe_extract_json(text: str):
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
        return json.loads(cleaned)
    except Exception:
        return [{"error": "Invalid JSON", "raw": text}]
