import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model, get_cross_encoder_model
import os
import google.generativeai as genai

DB_PATH = "data/codes.db"
INDEX_PATH = "index/codes_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"
CROSS_ENCODER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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


if USE_GEMINI and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
else:
    GEMINI_MODEL = None

GEMINI_PROMPT = """
You are a clinical documentation assistant.

Your task is to rewrite the following clinical text into a single concise sentence that preserves only medically relevant information for retrieval:
- Keep only key symptoms, diagnoses, and procedures/interventions.
- Remove demographics (age, gender), filler words, and redundant phrasing.
- Do not add interpretations beyond the input.
- Output should be one clean sentence suitable for embedding.

SOAP Text:
{soap}
"""

def _call_gemini(prompt: str, timeout_s: int = 6) -> str:
    """Call Gemini (safely) and parse JSON. Returns dict or raises."""
    if GEMINI_MODEL is None:
        raise RuntimeError("Gemini not available/configured.")
    resp = GEMINI_MODEL.generate_content(prompt)
    return resp.text.strip()

def search_codes(query: str):
    prompt = GEMINI_PROMPT.format(soap=query)
    soap = _call_gemini(prompt=prompt)
    print(f"Gemini cleaned soap: {soap}")
    # Step 1: Embed query with bi-encoder and retrieve top_k candidates
    embedding = np.array(embed_model.encode([soap], convert_to_numpy=True), dtype=np.float32)
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
