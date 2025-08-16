# app/core/search_service_codes.py
import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model
from typing import List, Dict, Any

# Define the paths for the database, index, and the embedding model
DB_PATH = "data/service_codes.db"
INDEX_PATH = "index/service_codes_index.faiss"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ----------------------------
# Initialization
# ----------------------------
# Load the embedding model once to avoid repeated loading
model = get_sentence_model(EMBED_MODEL)

# Load the FAISS index from a pre-built file
index = faiss.read_index(INDEX_PATH)

# Load codes from SQLite. Using check_same_thread=False is crucial for FastAPI
# as it allows the connection to be shared across multiple threads without issue.
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT id, description FROM service_codes ORDER BY id")
all_codes = cursor.fetchall()

# Sanity check: ensure the FAISS index and the database have the same number of items
if index.ntotal != len(all_codes):
    raise RuntimeError(
        f"FAISS index ({index.ntotal}) and DB rows ({len(all_codes)}) do not match. "
        "Please rebuild the index using `scripts/build_code_index.py`."
    )

def normalize_vector(v: np.ndarray) -> np.ndarray:
    """Normalize a vector to unit length for accurate cosine similarity."""
    norm = np.linalg.norm(v)
    return v.astype(np.float32) / (norm + 1e-10)

def search_service_codes(
    query: str,
    top_k: int = 10,
    min_similarity: float = 0.5,
    fallback: bool = True
) -> List[Dict[str, Any]]:
    """
    Finds and returns top-k service code candidates for a given SOAP note query.

    Returns a list of dictionaries, each containing 'code', 'description', and 'similarity'.
    Always returns a list (empty if nothing found) to avoid None issues.
    """
    # Generate a normalized embedding for the query
    embedding = normalize_vector(model.encode([query], convert_to_numpy=True)[0])

    # Search the FAISS index for the nearest neighbors
    D, I = index.search(np.array([embedding]), k=top_k)

    results = []
    for dist, idx in zip(D[0], I[0]):
        if idx < 0:
            continue

        # Convert L2 distance from FAISS to cosine similarity: sim = 1 - (dist^2 / 2)
        similarity = 1 - (dist ** 2) / 2

        # Filter results based on the minimum similarity threshold
        if similarity < min_similarity:
            continue

        code, desc = all_codes[idx]
        results.append({
            "code": code,
            "description": desc,
            "similarity": float(similarity)
        })

    # Fallback logic: always return the top candidate if results are empty
    if not results and fallback and len(I[0]) > 0 and I[0][0] >= 0:
        idx = I[0][0]
        code, desc = all_codes[idx]
        similarity = 1 - (D[0][0] ** 2) / 2
        results.append({
            "code": code,
            "description": desc,
            "similarity": float(similarity)
        })

    # Ensure a list is always returned
    return results or []

def get_service_code_descriptions(codes: List[str]) -> Dict[str, str]:
    """
    Fetches the descriptions for a given list of service codes.

    Returns a dictionary mapping code -> description.
    """
    code_set = set(codes)
    return {code: desc for code, desc in all_codes if code in code_set}
