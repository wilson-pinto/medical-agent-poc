import os
import pandas as pd
import sqlite3
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# --------- Config ---------
EXCEL_FILE = "data/icd10_norway.xlsx"
DB_FILE = "data/diagnosis_codes.db"
FAISS_FILE = "index/diagnosis_index.faiss"
EMBEDDING_MODEL = "NbAiLab/nb-sbert-base"
# --------------------------

def load_codes_from_excel(path):
    df = pd.read_excel(path)
    df.columns = [col.strip() for col in df.columns]
    df = df.rename(columns={
        "Kode": "code",
        "Tekst uten lengdebegrensning": "description"
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
    model = SentenceTransformer(EMBEDDING_MODEL)
    descriptions = [desc for _, desc in codes]
    embeddings = model.encode(descriptions, convert_to_numpy=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, FAISS_FILE)
    print(f"FAISS index saved to {FAISS_FILE}")

def main():
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
