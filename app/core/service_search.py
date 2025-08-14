import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model

DB_PATH = "data/codes.db"
INDEX_PATH = "index/codes_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"

# Load model
model = get_sentence_model(EMBED_MODEL)

# Load FAISS index
index = faiss.read_index(INDEX_PATH)

# Load DB
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT * FROM service_codes ORDER BY id")
all_codes = cursor.fetchall()

# --- Verification ---
if index.ntotal != len(all_codes):
    raise RuntimeError(
        f"[ERROR] FAISS index ({index.ntotal}) and DB rows ({len(all_codes)}) do not match. "
        f"Rebuild with `scripts/build_code_index.py`."
    )
# --------------------

def search_codes(query: str, top_k: int = 5):
    embedding = np.array(model.encode([query], convert_to_numpy=True), dtype=np.float32)
    D, I = index.search(embedding, k=top_k)
    matches = []
    for idx in I[0]:
        code_id, desc = all_codes[idx]
        matches.append(f"{code_id}: {desc}")
    return matches

def get_service_code_descriptions(codes: list[str]) -> dict:
    code_set = set(codes)
    result = {}
    for code_id, desc in all_codes:
        if code_id in code_set:
            result[code_id] = desc
    return result
