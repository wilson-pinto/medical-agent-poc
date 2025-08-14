import sqlite3
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"

model = SentenceTransformer(EMBED_MODEL)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT id, description FROM diagnosis_codes ORDER BY id")
rows = cursor.fetchall()

descriptions = [desc for _, desc in rows]
embeddings = model.encode(descriptions, convert_to_numpy=True)
embeddings = embeddings.astype(np.float32)

index = faiss.IndexFlatIP(embeddings.shape[1])
faiss.normalize_L2(embeddings)
index.add(embeddings)
faiss.write_index(index, INDEX_PATH)
print(f"Diagnosis FAISS index saved to {INDEX_PATH}")
