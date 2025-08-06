import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model


model = get_sentence_model("all-MiniLM-L6-v2")
index = faiss.read_index("index/codes_index.faiss")
conn = sqlite3.connect("data/codes.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT * FROM codes")
all_codes = cursor.fetchall()

def search_codes(query: str, top_k: int = 5):
    embedding = model.encode([query])
    D, I = index.search(np.array(embedding), k=top_k)
    matches = []
    for idx in I[0]:
        code_id, desc = all_codes[idx]
        matches.append(f"{code_id}: {desc}")
    return matches