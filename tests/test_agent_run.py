from app.agents.helfo_agent import HelfoAgent

# Test SOAP notes with different scenarios
test_soap_notes = [
    "Patient complains of a persistent headache for three days. No fever.",  # simple case
    "Patient reports chest pain and shortness of breath. No nausea.",          # multiple concepts
    "Patient has a rash on the arm. No other symptoms.",                      # triggers another missing term
    "",                                                                       # empty note
    "Patient reports fever and headache. No other complaints."                # negation + multiple symptoms
]

# Predefined answers for missing terms (simulate user input)
answers = {
    "q_clarification": "The patient needs clarification on billing.",
    # Add more question IDs and answers if your agent creates new ones
}

agent = HelfoAgent(user_id="test-user")

for idx, soap in enumerate(test_soap_notes, start=1):
    print(f"\n=== Running Test Case {idx} ===")
    validation = agent.run(soap)

    # Check pending questions
    questions = agent.get_pending_questions()
    while questions:
        print(f"Agent has {len(questions)} pending question(s). Auto-answering...")
        for q in questions:
            answer = answers.get(q["id"], "Default answer for testing.")
            agent.answer_question(q["id"], answer)
        questions = agent.get_pending_questions()

    print(f"Final validation results for Test Case {idx}:")
    print(validation)
