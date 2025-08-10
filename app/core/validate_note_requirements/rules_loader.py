# app/core/validate_note_requirements/rules_loader.py
import yaml
import os
from functools import lru_cache

RULES_FILE = os.path.join("data", "takst_rules.yaml")

@lru_cache(maxsize=1)
def load_rules():
    """Load takst rules from YAML and return as dict keyed by service code (string)."""
    if not os.path.exists(RULES_FILE):
        raise FileNotFoundError(f"Rules file not found: {RULES_FILE}")
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Ensure keys are strings & normalized
    normalized = {str(k).strip(): v for k, v in (data or {}).items()}
    return normalized
