# diagnosis_search.py
import faiss
import sqlite3
import numpy as np
from app.core.sentence_model_registry import get_sentence_model
from app.core.rerankers.cross_encoder import rerank_documents
import collections

DB_PATH = "data/diagnosis_codes.db"
INDEX_PATH = "index/diagnosis_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"

# Explicitly define the chosen reranker model for clarity and robustness
RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """
    Normalize vectors to unit length for cosine similarity.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / (norms + 1e-10)

# --------------------
# Load model & data
# --------------------
# Initialize the bi-encoder model
model = get_sentence_model(EMBED_MODEL)

# Load the FAISS index for fast initial retrieval
index = faiss.read_index(INDEX_PATH)

# Load diagnosis codes from the database
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("SELECT * FROM diagnosis_codes ORDER BY id")
all_codes = cursor.fetchall()

# Create a mapping from document text to its full (code, description) tuple
# This is necessary because the reranker works on text, so we need to map back
# to the original code. Using an OrderedDict to preserve insertion order.
DOC_ID_MAPPING = collections.OrderedDict()
for code, description in all_codes:
    DOC_ID_MAPPING[description] = (code, description)

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
    initial_k: int = 50,  # New parameter for initial FAISS retrieval
    min_similarity: float = 0.6,
    return_raw: bool = False
):
    """
    Searches for diagnosis codes using a two-step retrieval and reranking process.

    1. Initial retrieval: Uses FAISS to get a larger pool of potential matches (initial_k).
    2. Reranking: Uses a cross-encoder model to sort these matches by true relevance.
    3. Final selection: Takes the top_k results from the reranked list.
    """
    results = []

    for concept in grouped_concepts:
        print(f"[DEBUG] Searching concept: '{concept}'")

        # Step 1: Initial Retrieval with FAISS
        embedding = np.array(model.encode([concept], convert_to_numpy=True), dtype=np.float32)
        embedding = normalize_vectors(embedding)

        # Get a larger number of candidates to rerank
        D, I = index.search(embedding, k=initial_k)

        initial_candidate_docs = []
        for idx in I[0]:
            if idx != -1:
                initial_candidate_docs.append(all_codes[idx][1])

        print(f"[DEBUG] Retrieved {len(initial_candidate_docs)} candidates from FAISS for reranking.")

        # Step 2: Rerank the initial candidates using the cross-encoder
        # Pass the specific model name here
        reranked_docs_with_scores = rerank_documents(
            concept,
            initial_candidate_docs,
            model_name=RERANKER_MODEL
        )

        # Step 3: Select the top_k results from the reranked list
        concept_matches = []
        for doc_text, score in reranked_docs_with_scores[:top_k]:
            original_code, original_description = DOC_ID_MAPPING[doc_text]

            reason = (
                f"Matched because the concept text closely aligns with ICD-10 description "
                f"'{original_description}' (cross-encoder score: {score:.2f})."
            )

            concept_matches.append({
                "code": original_code,
                "description": original_description,
                "reason": reason,
                "similarity": float(score)
            })

        if not concept_matches and not return_raw:
            print(f"  [DEBUG] No matches found for concept '{concept}' after reranking.")
            concept_matches.append({
                "code": None,
                "description": None,
                "reason": f"No ICD-10 matches found for concept '{concept}'",
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

# --- Direct test block for the new logic ---
if __name__ == "__main__":
    test_concepts = [
        "kolera som skyldes Vibrio cholerae",
        "salmonellaenteritt",
        "tuberkulose i øye"
    ]
    print("--- Running direct test of search_diagnosis_with_explanation ---")
    test_results = search_diagnosis_with_explanation(test_concepts, top_k=5)

    import json
    print(json.dumps(test_results, indent=2))
    print("--- Direct test complete ---")
