# app/agents/helfo_validator/question_planner.py

from typing import List, Dict
import uuid

def plan_questions_from_missing(missing_terms: List[str]) -> List[Dict]:
    """
    Given a list of missing terms from validation, generate
    question prompts for the user to fill in missing info.

    Returns list of dicts like:
    [
        {"id": "<uuid>", "question": "Please provide ..."}
    ]
    """
    questions = []
    for term in missing_terms:
        q = {
            "id": str(uuid.uuid4()),
            "question": f"Please provide details for missing documentation: '{term}'"
        }
        questions.append(q)
    return questions
