from openai import OpenAI
from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def rerank_with_openai(query: str, candidates: list[str]) -> str:
    system_prompt = "You are a medical billing assistant. You help select the best matching medical code based on user input."
    user_prompt = f"A user entered the query: '{query}'\nSelect the most appropriate service code from the list below:\n" + \
                   "\n".join(f"{i+1}. {c}" for i, c in enumerate(candidates)) + "\n\nRespond with only the code ID and a short reasoning."

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()
