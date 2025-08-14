# app/data/soap_notes_examples.py

soap_notes_examples = [
    {
        "id": 1,
        "text": "The patient has a fever of 38.5°C and was advised to rest and drink plenty of fluids.",  # fever
        "expected_codes": ["MT001"],  # triggers temperature/fever check
    },
    {
        "id": 2,
        "text": "Blood pressure measured at 140/90 mmHg, patient assessed for mild hypertension.",
        "expected_codes": ["MT002"],  # triggers blood pressure/assessment
    },
    {
        "id": 3,
        "text": "The patient complains of headache and mild dizziness.",
        "expected_codes": [],  # no required terms met
    },
]
