# tests/test_helfo_agent_mock.py
from unittest.mock import patch
import json
import pytest
from app.agents.helfo_agent import HelfoAgent

mock_gemini_response = {
    "reasoning": "Candidate code seems appropriate based on SOAP note content.",
    "recommended_action": "No further action required."
}

def run_agent_with_mock_gemini(agent, soap_note):
    with patch("app.agents.helfo_agent.GEMINI_MODEL.generate_content") as mock_generate:
        mock_generate.return_value.text = json.dumps(mock_gemini_response)
        result = agent.run(soap_note)
    return result

def test_helfo_agent_with_mock_gemini():
    agent = HelfoAgent(user_id="test_user")
    soap_note = "Patient has fever of 38.5°C, advised to rest and hydrate."
    result = run_agent_with_mock_gemini(agent, soap_note)

    # Simple assertions
    assert "service_codes" in result
    for code in result["service_codes"]:
        assert "gemini_reasoning" in code
        assert "recommended_action" in code
