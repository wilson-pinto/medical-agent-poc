from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from app.utils.pii.norwegian_fnr_recognizer import NorwegianFNRRecognizer
from app.utils.pii.norwegian_phone_recognizer import NorwegianPhoneRecognizer
from app.utils.pii.norwegian_address_recognizer import NorwegianAddressRecognizer

nlp_engine = AnalyzerEngine()
analyzer = AnalyzerEngine()
analyzer.registry.add_recognizer(NorwegianFNRRecognizer())
analyzer.registry.add_recognizer(NorwegianPhoneRecognizer())
analyzer.registry.add_recognizer(NorwegianAddressRecognizer())
anonymizer = AnonymizerEngine()

def anonymize_soap(text: str) -> str:
    entities = analyzer.analyze(text=text, language="no")
    return anonymizer.anonymize(text, analyzer_results=entities).text
