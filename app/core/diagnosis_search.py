#diagnosis_search.py
import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model, get_cross_encoder_model
import torch
import json

DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"
CROSS_ENCODER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """
    Normalize vectors to unit length for cosine similarity.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / (norms + 1e-10)

# --------------------
# Load model & data
# --------------------
sentence_model = get_sentence_model(EMBED_MODEL)
cross_encoder_model = get_cross_encoder_model(CROSS_ENCODER)
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
    return_raw: bool = False,
    initial_k: int = 50  # how many candidates to fetch first from FAISS
):
    results = []

    for concept in grouped_concepts:
        print(f"[DEBUG] Searching concept: '{concept}'")

        # ---- Stage 1: Sentence model + FAISS ----
        embedding = np.array(sentence_model.encode([concept], convert_to_numpy=True), dtype=np.float32)
        embedding = normalize_vectors(embedding)
        D, I = index.search(embedding, k=initial_k)

        def to_serializable(obj):
            if isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            if isinstance(obj, (np.int32, np.int64)):
                return int(obj)
            return str(obj)

        candidates = []
        for dist, idx in zip(D[0], I[0]):
            if idx == -1:
                continue
            code, description = all_codes[idx]
            similarity_score = 1 - (dist ** 2) / 2
            candidates.append((code, description, similarity_score))

        print("---------------------------------------------------")
        print(f"Initial FAISS search results for '{concept}':")
        print(f"Candidates: {json.dumps(candidates, indent=2, ensure_ascii=False, default=to_serializable)}")

        if not candidates:
            results.append({
                "concept": concept,
                "matches": [{
                    "code": None,
                    "description": None,
                    "reason": "No FAISS candidates found",
                    "similarity": None
                }]
            })
            continue

        # ---- Stage 2: Re-rank with cross-encoder ----
        ce_inputs = [(concept, desc) for _, desc, _ in candidates]
        ce_scores = cross_encoder_model.predict(ce_inputs)
        ce_scores = torch.sigmoid(torch.tensor(ce_scores)).numpy()

        # Attach CE scores to candidates
        reranked = [
            {
                "code": code,
                "description": description,
                "reason": (
                    f"Cross-encoder re-ranked match. Original FAISS similarity: {sim:.2f}, "
                    f"cross-encoder score: {score:.2f}."
                ),
                "similarity": float(score)
            }
            for (code, description, sim), score in zip(candidates, ce_scores)
        ]

        # Sort by cross-encoder score
        reranked = sorted(reranked, key=lambda x: x["similarity"], reverse=True)

        print(f"Renranked: {json.dumps(reranked, indent=2, ensure_ascii=False, default=to_serializable)}")

        # Keep only top_k, and apply min_similarity if return_raw=False
        final_matches = []
        for match in reranked[:top_k]:
            if not return_raw and match["similarity"] < min_similarity:
                continue
            final_matches.append(match)

        if not final_matches and not return_raw:
            final_matches.append({
                "code": None,
                "description": None,
                "reason": f"No ICD-10 matches above similarity threshold {min_similarity}",
                "similarity": None
            })

        results.append({
            "concept": concept,
            "matches": final_matches
        })

    print(f"[DEBUG] Finished searching {len(grouped_concepts)} concepts.")
    print(f"Results from Encoders: {results}")
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
