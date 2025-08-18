import json
import numpy as np
from app.core.claim_learning_engine import FAISS_INDEX, embed_model, DB_CURSOR, _normalize_embeddings
from app.core.pii_analyzer import anonymize_text

TOP_K_SIMILAR_PREDICT = 5
SIM_THRESHOLD_PREDICT = 0.3  # 0.3 = 30% similarity

def get_similar_failures(anon_soap: str, service_codes: list) -> list[dict]:
    """
    Returns top similar learned failures above the threshold.
    Each entry is a dict with 'score' and 'suggestions'.
    """
    if FAISS_INDEX.ntotal == 0:
        return []

    # Generate and normalize embedding
    embedding = embed_model.encode([anon_soap], convert_to_numpy=True).astype(np.float32)
    normalized_embedding = _normalize_embeddings(embedding)

    # Search using L2 distance
    D, I = FAISS_INDEX.search(normalized_embedding, TOP_K_SIMILAR_PREDICT)

    similar_failures = []
    for l2_distance, idx in zip(D[0], I[0]):
        # Skip invalid indices (FAISS returns -1 for empty slots)
        if idx == -1:
            continue

        # Convert L2 distance to similarity score (0-1)
        # For normalized vectors, L2 distance ranges from 0 to 2
        similarity_score = max(0, 1 - (l2_distance / 2))

        if similarity_score < SIM_THRESHOLD_PREDICT:
            continue

        # Use idx directly as it's the actual DB row ID from IndexIDMap
        try:
            DB_CURSOR.execute("SELECT service_codes, suggestions FROM claim_learning WHERE id=?", (int(idx),))
            row = DB_CURSOR.fetchone()
            if not row:
                continue
        except Exception as e:
            print(f"Database error for idx {idx}: {e}")
            continue

        stored_codes_str, stored_suggestions_json = row
        stored_codes = stored_codes_str.split(",")

        # Only consider entries with matching service codes
        if sorted(stored_codes) != sorted(service_codes):
            continue

        # Handle potential JSON decode errors
        try:
            suggestions = json.loads(stored_suggestions_json) if stored_suggestions_json else []
        except json.JSONDecodeError:
            suggestions = []

        similar_failures.append({
            "score": float(similarity_score),  # Now properly normalized 0-1
            "suggestions": suggestions
        })

    return similar_failures

def calculate_rejection_probability(similar_failures: list[dict]) -> float:
    """
    Returns rejection probability as a float between 0 and 1.
    Now works with properly normalized similarity scores (0-1).
    """
    if not similar_failures:
        return 0.15  # Low baseline probability

    scores = [f["score"] for f in similar_failures]
    num_failures = len(similar_failures)

    # Calculate weighted probability based on similarity scores
    avg_score = np.mean(scores)

    # More conservative probability calculation to spread out the ranges
    # Scale down the similarity impact to create more medium-risk scenarios
    base_prob = avg_score * 0.7  # Reduced from 0.9 to 0.7

    # Small boost for multiple failures
    volume_boost = min(0.05, (num_failures - 1) * 0.01)

    # Add some baseline risk even for low similarity
    baseline_risk = 0.2

    # Final probability: blend baseline risk with similarity-based risk
    final_prob = baseline_risk + (base_prob + volume_boost) * 0.8

    # Ensure it's within reasonable bounds
    final_prob = np.clip(final_prob, 0.15, 0.85)

    return float(final_prob)

def assign_risk_level(prob: float) -> str:
    """
    Assigns risk level with more balanced thresholds for medium risk.
    """
    if prob >= 0.75:  # Raised threshold for high risk
        return "high"
    elif prob >= 0.25:  # Lowered threshold for medium risk
        return "medium"
    return "low"

def aggregate_suggestions(similar_failures: list[dict]) -> list[str]:
    """
    Aggregates suggestions with frequency weighting.
    """
    suggestion_counts = {}

    for f in similar_failures:
        for suggestion in f.get("suggestions", []):
            suggestion_counts[suggestion] = suggestion_counts.get(suggestion, 0) + 1

    # Sort by frequency and return unique suggestions
    sorted_suggestions = sorted(suggestion_counts.items(), key=lambda x: x[1], reverse=True)
    suggestions = [s[0] for s in sorted_suggestions]

    return suggestions or ["Ensure detailed clinical terms in SOAP note"]

# Additional helper function for testing different scenarios
def get_risk_breakdown(anon_soap: str, service_codes: list) -> dict:
    """
    Returns detailed breakdown for debugging/testing purposes.
    """
    similar_failures = get_similar_failures(anon_soap, service_codes)

    if not similar_failures:
        return {
            "similar_failures_count": 0,
            "scores": [],
            "avg_score": 0,
            "rejection_prob": 0.15,
            "risk_level": "low",
            "reason": "No similar failures found"
        }

    scores = [f["score"] for f in similar_failures]
    rejection_prob = calculate_rejection_probability(similar_failures)
    risk_level = assign_risk_level(rejection_prob)

    return {
        "similar_failures_count": len(similar_failures),
        "scores": scores,
        "avg_score": np.mean(scores),
        "max_score": np.max(scores),
        "min_score": np.min(scores),
        "score_std": np.std(scores) if len(scores) > 1 else 0,
        "rejection_prob": rejection_prob,
        "risk_level": risk_level,
        "reason": f"Found {len(similar_failures)} similar failure(s)"
    }