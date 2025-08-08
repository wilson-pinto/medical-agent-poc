import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model

DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"

model = get_sentence_model(EMBED_MODEL)
index = faiss.read_index(INDEX_PATH)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT * FROM diagnosis_codes")
all_codes = cursor.fetchall()

def search_diagnosis(query: str, top_k: int = 5):
    embedding = model.encode([query])
    D, I = index.search(np.array(embedding), k=top_k)
    matches = []
    for idx in I[0]:
        code, description = all_codes[idx]
        matches.append(f"{code}: {description}")
    return matches

def get_diagnosis_descriptions(codes: list[str]) -> dict:
    code_set = set(codes)
    result = {}
    for code, description in all_codes:
        if code in code_set:
            result[code] = description
    return result