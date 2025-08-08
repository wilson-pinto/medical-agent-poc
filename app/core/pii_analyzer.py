from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import SpacyNlpEngine, NlpEngineProvider
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_anonymizer import AnonymizerEngine

from app.utils.pii.norwegian_fnr_recognizer import NorwegianFNRRecognizer
from app.utils.pii.norwegian_phone_recognizer import NorwegianPhoneRecognizer
from app.utils.pii.norwegian_address_recognizer import NorwegianAddressRecognizer

provider = NlpEngineProvider(nlp_configuration={
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "no", "model_name": "nb_core_news_sm"}]
})
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["no"])

analyzer.registry.add_recognizer(SpacyRecognizer())  # handles PERSON, DATE_TIME, LOCATION, etc.
analyzer.registry.add_recognizer(NorwegianFNRRecognizer())
analyzer.registry.add_recognizer(NorwegianPhoneRecognizer())
analyzer.registry.add_recognizer(NorwegianAddressRecognizer())

anonymizer = AnonymizerEngine()

def analyze_text(text: str):
    return analyzer.analyze(text=text, language="no")

def anonymize_text(text: str, entities: list):
    return anonymizer.anonymize(text=text, analyzer_results=entities).text
