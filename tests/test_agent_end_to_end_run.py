# tests/test_agent_end_to_end_run.py
import json
from app.agents.helfo_agent import HelfoAgent

def main():
    user_id = "hackathon_user_001"
    agent = HelfoAgent(user_id=user_id)

    # ----------------------------
    # Sample SOAP note
    # ----------------------------
    sample_soap = """
    Patient complains of severe headache and mild nausea for two days.
    No fever or other symptoms. Clarification needed on prior medications.
    """

    print("\n=== Running Agent with Sample SOAP Note ===")
    validation_state = agent.run(sample_soap)

    print("\n--- Initial Validation Results ---")
    print(json.dumps(validation_state, indent=2))

    # ----------------------------
    # Check for pending questions
    # ----------------------------
    pending_questions = agent.get_pending_questions()
    if pending_questions:
        print(f"\nAgent has {len(pending_questions)} pending question(s):")
        for q in pending_questions:
            print(f"- ID: {q['id']}, Text: {q['text']}")

        # Answer the first question (simulate user input)
        first_q = pending_questions[0]
        print(f"\n=== Answering Question {first_q['id']} ===")
        agent.answer_question(first_q["id"], "Patient has taken paracetamol 500mg daily.")

        # Check updated validation
        updated_questions = agent.get_pending_questions()
        if not updated_questions:
            print("\nAll questions resolved. Validation complete!")
        else:
            print(f"\nRemaining questions: {len(updated_questions)}")

    else:
        print("\nNo pending questions. Validation complete!")

if __name__ == "__main__":
    main()
