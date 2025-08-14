# scripts/build_english_diagnosis_db_and_index.py
import sqlite3
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os

# ---------------- Paths ----------------
EXCEL_FILE = "data/ICD10_English_Sample.xlsx"
DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

os.makedirs("data", exist_ok=True)
os.makedirs("index", exist_ok=True)

# ---------------- Load Excel ----------------
df = pd.read_excel(EXCEL_FILE)

# Make sure columns exist
assert "Code" in df.columns and "Full Description (No Length Limit)" in df.columns

codes = df["Code"].astype(str).tolist()
descriptions = df["Full Description (No Length Limit)"].astype(str).tolist()

# ---------------- Build SQLite ----------------
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS diagnosis_codes (
    id TEXT PRIMARY KEY,
    description TEXT
)
""")
cursor.execute("DELETE FROM diagnosis_codes")  # clear existing
cursor.executemany(
    "INSERT INTO diagnosis_codes (id, description) VALUES (?, ?)",
    list(zip(codes, descriptions))
)
conn.commit()
conn.close()
print(f"Saved {len(codes)} ICD10 codes to {DB_PATH}")

# ---------------- Build FAISS ----------------
model = SentenceTransformer(EMBED_MODEL)
embeddings = model.encode(descriptions, convert_to_numpy=True).astype(np.float32)

# Normalize vectors for cosine similarity
faiss.normalize_L2(embeddings)

index = faiss.IndexFlatIP(embeddings.shape[1])  # Inner Product = cosine since vectors normalized
index.add(embeddings)

faiss.write_index(index, INDEX_PATH)
print(f"FAISS index saved to {INDEX_PATH}, total vectors: {index.ntotal}")
