# app/core/pii_pipeline.py
from app.core.pii_analyzer import analyze_text, anonymize_text

def anonymize_soap(soap: str) -> str:
    """
    Runs SOAP note through Presidio's Norwegian PII detection and anonymization.
    Returns anonymized text safe for LLM processing.
    """
    entities = analyze_text(soap)
    return anonymize_text(soap, entities)
