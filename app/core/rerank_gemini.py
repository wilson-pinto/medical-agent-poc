import google.generativeai as genai
from app.config import GEMINI_API_KEY

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

def get_best_code(query: str, candidates: list[str]) -> str:
    if not model:
        return "Gemini API key missing."

    prompt = f"""You are a medical billing assistant.
A user entered the query: \"{query}\"

Select the most appropriate service code from the list below:
"""
    for i, item in enumerate(candidates, 1):
        prompt += f"{i}. {item}\n"

    prompt += """
Respond with only the code ID and a short reasoning.
Example: MT001 - This matches spine therapy.
"""

    response = model.generate_content(prompt)
    return response.text.strip()
