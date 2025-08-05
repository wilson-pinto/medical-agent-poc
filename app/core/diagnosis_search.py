import faiss
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer

DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"

model = SentenceTransformer(EMBED_MODEL)
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