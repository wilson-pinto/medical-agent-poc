from presidio_analyzer import Pattern, PatternRecognizer

class NorwegianFNRRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="FNR Pattern", regex=r"\b\d{11}\b", score=0.85)
        ]
        super().__init__(
            patterns=patterns,
            supported_entity="FNR",
            name="NorwegianFNRRecognizer",
            supported_language="no"
        )
