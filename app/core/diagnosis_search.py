#diagnosis_search.py
import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model

DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"

def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """
    Normalize vectors to unit length for cosine similarity.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / (norms + 1e-10)

# --------------------
# Load model & data
# --------------------
model = get_sentence_model(EMBED_MODEL)
index = faiss.read_index(INDEX_PATH)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT * FROM diagnosis_codes ORDER BY id")
all_codes = cursor.fetchall()

# --- Verification ---
if index.ntotal != len(all_codes):
    raise RuntimeError(
        f"[ERROR] FAISS index ({index.ntotal}) and DB rows ({len(all_codes)}) do not match. "
        f"Rebuild with `scripts/build_diagnosis_index.py`."
    )
# --------------------

def search_diagnosis_with_explanation(
    grouped_concepts: list[str],
    top_k: int = 3,
    min_similarity: float = 0.6,
    return_raw: bool = False
):
    results = []

    for concept in grouped_concepts:
        print(f"[DEBUG] Searching concept: '{concept}'")
        embedding = np.array(model.encode([concept], convert_to_numpy=True), dtype=np.float32)
        embedding = normalize_vectors(embedding)
        print(f"[DEBUG] Embedding vector (first 5 dims): {embedding[0][:5]}")  # show snippet of embedding

        D, I = index.search(embedding, k=top_k)
        print(f"[DEBUG] FAISS distances: {D[0]}")
        print(f"[DEBUG] FAISS indices: {I[0]}")

        concept_matches = []
        for dist, idx in zip(D[0], I[0]):
            if idx == -1:
                continue

            code, description = all_codes[idx]
            similarity_score = 1 - (dist ** 2) / 2
            print(f"  [DEBUG] Candidate code: {code}, similarity_score: {similarity_score:.4f}")

            # Filter by similarity if return_raw is False
            if not return_raw and similarity_score < min_similarity:
                print(f"  [DEBUG] Skipping {code} due to low similarity ({similarity_score:.4f} < {min_similarity})")
                continue

            reason = (
                f"Matched because the concept text closely aligns with ICD-10 description "
                f"'{description}' (similarity score: {similarity_score:.2f})."
            )

            concept_matches.append({
                "code": code,
                "description": description,
                "reason": reason,
                "similarity": float(similarity_score)
            })

        if not concept_matches and not return_raw:
            print(f"  [DEBUG] No matches above similarity threshold {min_similarity} for concept '{concept}'")
            concept_matches.append({
                "code": None,
                "description": None,
                "reason": f"No ICD-10 matches above similarity threshold {min_similarity}",
                "similarity": None
            })

        results.append({
            "concept": concept,
            "matches": concept_matches
        })

    print(f"[DEBUG] Finished searching {len(grouped_concepts)} concepts.")
    return {"diagnoses": results}


def get_diagnosis_descriptions(codes: list[str]) -> dict:
    """
    Given a list of codes, return { code: description } mapping.
    """
    code_set = set(codes)
    result = {}
    for code, description in all_codes:
        if code in code_set:
            result[code] = description
    return result
