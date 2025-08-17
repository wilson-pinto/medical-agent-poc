import os
import argparse
import pandas as pd
import sqlite3
import faiss
import numpy as np
from app.core.sentence_model_registry import get_sentence_model

# --------- Config ---------
EXCEL_FILE = "data/icd10_english.xlsx"
DB_FILE = "data/diagnosis_codes.db"
FAISS_FILE = "index/diagnosis_index.faiss"
EMBEDDING_MODEL = "NbAiLab/nb-sbert-base"
# --------------------------

def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / (norms + 1e-10)

def load_codes_from_excel(path):
    df = pd.read_excel(path)
    df.columns = [col.strip() for col in df.columns]
    df = df.rename(columns={
        "Code": "code",
        "Long Description": "description"
    })
    df = df[["code", "description"]].dropna()
    return list(df.itertuples(index=False, name=None))

def save_to_sqlite(codes):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS diagnosis_codes")
    cur.execute("CREATE TABLE diagnosis_codes (id TEXT, description TEXT)")
    cur.executemany("INSERT INTO diagnosis_codes VALUES (?, ?)", codes)
    conn.commit()
    conn.close()

def build_faiss_index(codes):
    model = get_sentence_model(EMBEDDING_MODEL)
    descriptions = [desc for _, desc in codes]
    embeddings = model.encode(descriptions, convert_to_numpy=True)

    # Normalize embeddings
    embeddings = normalize_vectors(embeddings).astype(np.float32)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner Product works with normalized vectors as cosine similarity
    index.add(embeddings)

    faiss.write_index(index, FAISS_FILE)
    print(f"FAISS index saved to {FAISS_FILE}")

def verify_index():
    if not os.path.exists(DB_FILE) or not os.path.exists(FAISS_FILE):
        print("[ERROR] Missing DB or FAISS index file.")
        return False

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM diagnosis_codes")
    db_count = cur.fetchone()[0]
    conn.close()

    index = faiss.read_index(FAISS_FILE)
    faiss_count = index.ntotal

    if db_count != faiss_count:
        print(f"[FAIL] Mismatch: DB has {db_count} codes, FAISS has {faiss_count} embeddings.")
        return False

    print(f"[PASS] DB and FAISS index match: {db_count} codes.")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="Verify DB ↔ FAISS consistency")
    args = parser.parse_args()

    if args.verify:
        verify_index()
        return

    if not os.path.exists(EXCEL_FILE):
        print(f"Excel file not found at {EXCEL_FILE}")
        return

    codes = load_codes_from_excel(EXCEL_FILE)
    print(f"Loaded {len(codes)} diagnosis codes")

    save_to_sqlite(codes)
    print(f"Saved to SQLite at {DB_FILE}")

    build_faiss_index(codes)

if __name__ == "__main__":
    main()
