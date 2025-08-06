from fastapi import FastAPI
from pydantic import BaseModel
import faiss
import numpy as np
import sqlite3
import os
from openai import OpenAI
from app.core.sentence_model_registry import get_sentence_model

app = FastAPI()

# -------------- Setup --------------------
embedding_model = get_sentence_model("all-MiniLM-L6-v2")

# Load FAISS index
faiss_index = faiss.read_index("index/codes_index.faiss")

# Load SQLite codes
conn = sqlite3.connect("data/codes.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT * FROM codes")
all_codes = cursor.fetchall()

# Initialize OpenAI client (uses OPENAI_API_KEY from environment)
client = OpenAI()
# ----------------------------------------


# --------- Request Models ---------------
class QueryRequest(BaseModel):
    session_id: str
    query: str
    top_k: int = 5

class RerankRequest(BaseModel):
    session_id: str
    query: str
    candidates: list[str]
# ----------------------------------------


@app.post("/agent/search/invoke")
def search_agent(payload: QueryRequest):
    embedding = embedding_model.encode([payload.query])
    D, I = faiss_index.search(np.array(embedding), k=payload.top_k)

    matches = []
    for idx in I[0]:
        code_id, desc = all_codes[idx]
        matches.append(f"{code_id}: {desc}")

    return {
        "session_id": payload.session_id,
        "candidates": matches
    }


@app.post("/agent/rerank/invoke")
def rerank_agent(payload: RerankRequest):
    system_prompt = """You are a medical billing assistant. You help select the best matching medical code based on user input."""

    user_prompt = f"""A user entered the query: "{payload.query}"

Select the most appropriate service code from the list below:

"""

    for i, item in enumerate(payload.candidates, 1):
        user_prompt += f"{i}. {item}\n"

    user_prompt += """
Respond with only the code ID and a short reasoning.
Example: MT001 - This matches spine therapy.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2
    )

    return {
        "session_id": payload.session_id,
        "decision": response.choices[0].message.content.strip()
    }


@app.get("/agent/formatter/invoke")
def formatter_agent(session_id: str, result: str):
    return {
        "session_id": session_id,
        "message": f"Best matching code: {result}"
    }
