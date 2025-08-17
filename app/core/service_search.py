import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model, get_cross_encoder_model

DB_PATH = "data/codes.db"
INDEX_PATH = "index/codes_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"
CROSS_ENCODER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# Load model
embed_model = get_sentence_model(EMBED_MODEL)
cross_encoder = get_cross_encoder_model(CROSS_ENCODER)

# Load FAISS index
index = faiss.read_index(INDEX_PATH)

# Load DB
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT * FROM codes ORDER BY id")
all_codes = cursor.fetchall()

# --- Verification ---
if index.ntotal != len(all_codes):
    raise RuntimeError(
        f"[ERROR] FAISS index ({index.ntotal}) and DB rows ({len(all_codes)}) do not match. "
        f"Rebuild with `scripts/build_code_index.py`."
    )
# --------------------

def search_codes(query: str, top_k: int = 5):
    # Step 1: Embed query with bi-encoder and retrieve top_k candidates
    embedding = np.array(embed_model.encode([query], convert_to_numpy=True), dtype=np.float32)
    D, I = index.search(embedding, k=50)

    candidates = []
    for score, idx in zip(D[0], I[0]):
        code_id, desc = all_codes[idx]
        candidates.append({
            "code": code_id,
            "description": desc,
            "faiss_score": float(score),
        })

    # Step 2: Re-rank with cross-encoder
    ce_inputs = [(query, c["description"]) for c in candidates]
    ce_scores = cross_encoder.predict(ce_inputs)

    for c, ce_score in zip(candidates, ce_scores):
        c["cross_score"] = float(ce_score)

    # Sort by cross-encoder score (higher = better)
    candidates = sorted(candidates, key=lambda x: x["cross_score"], reverse=True)

    return candidates

def get_service_code_descriptions(codes: list[str]) -> dict:
    code_set = set(codes)
    result = {}
    for code_id, desc in all_codes:
        if code_id in code_set:
            result[code_id] = desc
    return result
