from sentence_transformers import CrossEncoder
from typing import List, Dict

# Load a cross-encoder model (Norwegian or multilingual if possible)
MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-12-v2"  # placeholder; replace with NB fine-tuned if available
cross_encoder = CrossEncoder(MODEL_NAME)

def rerank_candidates(query: str, candidates: List[str], top_k: int = 5) -> List[Dict]:
    """
    Rerank service code candidates using cross-encoder.
    Returns a list of dicts: {code, reason, score}
    """
    if not candidates:
        return []

    # Pair query with each candidate
    pairs = [[query, candidate] for candidate in candidates]
    scores = cross_encoder.predict(pairs)  # higher = better

    # Zip and sort
    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True
    )

    results = []
    for candidate, score in ranked[:top_k]:
        code = candidate.split(":")[0]  # extract code from "CODE: description"
        reason = f"Cross-encoder score {score:.3f} indicates strong semantic alignment."
        results.append({
            "code": code,
            "reason": reason,
            "score": float(score)
        })
    return results
