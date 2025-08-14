import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model

DB_PATH = "data/service_codes.db"
INDEX_PATH = "index/service_codes_index.faiss"
# EMBED_MODEL = "NbAiLab/nb-sbert-base"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# Load embedding model
model = get_sentence_model(EMBED_MODEL)

# Load FAISS index
index = faiss.read_index(INDEX_PATH)

# Load codes from SQLite
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT id, description FROM service_codes ORDER BY id")
all_codes = cursor.fetchall()

if index.ntotal != len(all_codes):
    raise RuntimeError(
        f"FAISS index ({index.ntotal}) and DB rows ({len(all_codes)}) do not match. "
        "Rebuild index using `scripts/build_code_index.py`."
    )

def normalize_vector(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / (norm + 1e-10)




def search_service_codes(query: str, top_k: int = 10, min_similarity: float = 0.5) -> list[dict]:
    """
    Returns top-k service code candidates for a SOAP note query.
    Each entry includes code, description, and similarity score.
    """
    embedding = normalize_vector(model.encode([query], convert_to_numpy=True)[0]).astype(np.float32)
    D, I = index.search(np.array([embedding]), k=top_k)

    results = []
    for dist, idx in zip(D[0], I[0]):
        if idx < 0:
            continue
        similarity = 1 - (dist ** 2) / 2  # cosine similarity from squared L2
        if similarity < min_similarity:
            continue
        code, desc = all_codes[idx]
        results.append({
            "code": code,
            "description": desc,
            "similarity": float(similarity)
        })
    return results

def get_service_code_descriptions(codes: list[str]) -> dict:
    code_set = set(codes)
    return {code: desc for code, desc in all_codes if code in code_set}
