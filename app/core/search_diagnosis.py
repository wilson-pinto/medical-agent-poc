import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model

# DB_PATH = "data/diagnosis_codes.db"
# INDEX_PATH = "index/diagnosis_index.faiss"
# EMBED_MODEL = "NbAiLab/nb-sbert-base"
DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# Load embedding model
model = get_sentence_model(EMBED_MODEL)

# Load FAISS index
index = faiss.read_index(INDEX_PATH)

# Load diagnosis codes from SQLite
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT id, description FROM diagnosis_codes ORDER BY id")
all_codes = cursor.fetchall()

if index.ntotal != len(all_codes):
    raise RuntimeError(
        f"FAISS index ({index.ntotal}) != DB rows ({len(all_codes)})"
    )

def normalize_vector(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / (norm + 1e-10)

def search_diagnosis_with_explanation(
    concepts: list[str],
    top_k: int = 3,
    min_similarity: float = 0.6
) -> dict:
    """
    Returns top-k ICD/ICPC candidates for each concept.
    Each entry includes code, description, similarity, and reason.
    """
    results = []
    for concept in concepts:
        embedding = normalize_vector(model.encode([concept], convert_to_numpy=True)[0]).astype(np.float32)
        D, I = index.search(np.array([embedding]), k=top_k)
        matches = []
        for dist, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            similarity = 1 - (dist ** 2) / 2
            if similarity < min_similarity:
                continue
            code, desc = all_codes[idx]
            matches.append({
                "code": code,
                "description": desc,
                "similarity": float(similarity),
                "reason": f"Semantic match for concept '{concept}'"
            })
        results.append({"concept": concept, "matches": matches})
    return {"diagnoses": results}

def get_diagnosis_descriptions(codes: list[str]) -> dict:
    code_set = set(codes)
    return {code: desc for code, desc in all_codes if code in code_set}
