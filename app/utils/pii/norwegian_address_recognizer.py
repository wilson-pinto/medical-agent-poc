from presidio_analyzer import Pattern, PatternRecognizer

class NorwegianAddressRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(
                name="Norwegian Address Pattern",
                regex=r"\b(?:[A-ZÆØÅa-zæøå]+\s){1,3}\d{1,3}[A-Z]?\b",
                score=0.70
            )
        ]
        super().__init__(
            patterns=patterns,
            supported_entity="ADDRESS",
            name="NorwegianAddressRecognizer",
            supported_language="no"
        )
