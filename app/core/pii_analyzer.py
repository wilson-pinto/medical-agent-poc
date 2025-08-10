import os
import re
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_anonymizer import AnonymizerEngine

from app.utils.pii.norwegian_fnr_recognizer import NorwegianFNRRecognizer
from app.utils.pii.norwegian_phone_recognizer import NorwegianPhoneRecognizer
from app.utils.pii.norwegian_address_recognizer import NorwegianAddressRecognizer

# -------- Config --------
WHITELIST_FILE = "data/pii_whitelist.txt"
LANG_CODE = "no"

# Regex for ICD-10 (e.g., A01, B20.1) and ICPC (e.g., K50, L03.1)
ICD_CODE_REGEX = re.compile(r"\b([A-TV-Z][0-9]{2}(?:\.[0-9A-Z]{1,2})?)\b", re.IGNORECASE)
ICPC_CODE_REGEX = re.compile(r"\b([A-Z]{1,2}[0-9]{1,2}(?:\.[0-9])?)\b", re.IGNORECASE)

# Load whitelist terms (uppercased for case-insensitive matching)
if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
        WHITELIST = {line.strip().upper() for line in f if line.strip()}
else:
    WHITELIST = set()

# ------------------------

# Initialize NLP Engine for Norwegian
provider = NlpEngineProvider(nlp_configuration={
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": LANG_CODE, "model_name": "nb_core_news_sm"}]
})
nlp_engine = provider.create_engine()

# Analyzer with default + custom recognizers
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[LANG_CODE])
analyzer.registry.add_recognizer(SpacyRecognizer())  # PERSON, LOCATION, ORG, etc.
analyzer.registry.add_recognizer(NorwegianFNRRecognizer())
analyzer.registry.add_recognizer(NorwegianPhoneRecognizer())
analyzer.registry.add_recognizer(NorwegianAddressRecognizer())

anonymizer = AnonymizerEngine()

def is_whitelisted(term: str) -> bool:
    """Check if a detected term should be preserved."""
    if not term:
        return False
    term_upper = term.upper()
    # Medical whitelist terms
    if term_upper in WHITELIST:
        return True
    # ICD / ICPC code patterns
    if ICD_CODE_REGEX.fullmatch(term_upper) or ICPC_CODE_REGEX.fullmatch(term_upper):
        return True
    return False

def analyze_text(text: str):
    """Analyze and return detected entities, filtering out whitelisted terms."""
    entities = analyzer.analyze(text=text, language=LANG_CODE)

    filtered_entities = []
    for ent in entities:
        ent_text = text[ent.start:ent.end]
        if not is_whitelisted(ent_text):
            filtered_entities.append(ent)

    return filtered_entities


def anonymize_text(text: str, entities: list):
    """Anonymize only the filtered entities."""
    return anonymizer.anonymize(text=text, analyzer_results=entities).text
