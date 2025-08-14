# tests/test_agent_minimal.py
import pytest
from app.agents.helfo_agent import HelfoAgent

def test_agent_run_and_answer():
    agent = HelfoAgent(user_id="test-user")

    # Minimal SOAP note
    soap_note = "Patient complains of a headache."

    # Run the agent
    validation = agent.run(soap_note)

    # Check that validation results exist
    assert "results" in validation
    for r in validation["results"]:
        assert "code" in r
        assert "valid" in r
        assert "missing_terms" in r

    # Check that at least one pending question was generated
    questions = agent.get_pending_questions()
    assert len(questions) > 0
    first_q = questions[0]

    # Answer the first question
    agent.answer_question(first_q["id"], "Patient requires clarification on billing.")

    # After answering, pending questions should be empty
    final_questions = agent.get_pending_questions()
    assert final_questions == []

    # Validation results should now be all valid
    for r in agent.current_state["validation_results"]["results"]:
        assert r["valid"] is True
        assert r["missing_terms"] == []

    print("Minimal end-to-end test passed!")
