from presidio_analyzer import Pattern, PatternRecognizer

class NorwegianPhoneRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="Norwegian Phone Pattern", regex=r"\b\d{8}\b", score=0.85)
        ]
        super().__init__(
            patterns=patterns,
            supported_entity="PHONE_NUMBER",
            name="NorwegianPhoneRecognizer",
            supported_language="no"
        )
