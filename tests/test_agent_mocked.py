import pytest
from app.agents.helfo_agent import HelfoAgent

# Mock GEMINI_MODEL in the agent to avoid actual API calls
class MockGeminiModel:
    def generate_content(self, prompt, generation_config=None):
        class Response:
            text = '{"code": "C1", "reasoning": "Mock reasoning"}'
        return Response()

# Patch the agent before running
def patched_agent():
    agent = HelfoAgent(user_id="test-user")
    agent.GEMINI_MODEL = MockGeminiModel()  # Inject mock
    return agent

def test_agent_with_mocked_gemini():
    agent = patched_agent()
    soap_note = "Patient presents with mild abdominal pain and no fever."

    # Run agent
    validation = agent.run(soap_note)

    # Ensure pending questions exist (as expected)
    pending = agent.get_pending_questions()
    assert len(pending) > 0

    # Answer the question
    first_q = pending[0]
    agent.answer_question(first_q["id"], "Patient provided necessary details.")

    # After answering, no pending questions should remain
    final_pending = agent.get_pending_questions()
    assert len(final_pending) == 0

    # Validation results should now be marked valid
    results = agent.current_state["validation_results"]["results"]
    for r in results:
        assert r["valid"] is True

    print("Mocked Gemini test passed!")
