from app.agents.helfo_agent import HelfoAgent

def test_agent_end_to_end():
    # Initialize agent
    agent = HelfoAgent(user_id="test-user")

    # Step 1: Run with incomplete SOAP note
    soap_note = "Patient complains of a headache."
    validation = agent.run(soap_note)

    # Confirm initial validation fails
    assert all(r["valid"] is False for r in validation["results"])
    questions = agent.get_pending_questions()
    assert len(questions) > 0

    # Step 2: Simulate answering the first question
    first_q = questions[0]
    agent.answer_question(first_q["id"], "Patient requires clarification on billing.")

    # Step 3: Check final validation
    final_validation = agent.current_state["validation_results"]
    assert all(r["valid"] is True for r in final_validation["results"])
    assert len(agent.get_pending_questions()) == 0

    print("End-to-end test passed!")

if __name__ == "__main__":
    test_agent_end_to_end()
