# app/core/claim_learning_engine.py
import os
import json
import sqlite3
import faiss
import numpy as np
import logging
from typing import List, Dict, Any

from app.core.pii_analyzer import analyze_text, anonymize_text
from app.core.sentence_model_registry import get_sentence_model
from app.core.validate_note_requirements.engine import validate_soap_against_codes
from app.schemas import ClaimRejectionRequest, ClaimRejectionResponse
from app.schemas_new.validate_note_requirements import CheckNoteResponse, PerCodeResult

# Configure logging at the module level (best practice)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# -------------------------------
# CONFIG
# -------------------------------
EMBED_MODEL = "NbAiLab/nb-sbert-base"
DB_PATH = "data/claim_learning.db"
INDEX_PATH = "index/claim_learning.faiss"
TOP_K_SIMILAR = 1
SIM_THRESHOLD = 0.75

# -------------------------------
# Load embedding model (Moved to be defined before it's used)
# -------------------------------
embed_model = get_sentence_model(EMBED_MODEL)

# -------------------------------
# SQLite setup
# -------------------------------
def _init_db():
    """Initializes the SQLite database and table."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claim_learning (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faiss_id INTEGER UNIQUE,
        claim_id TEXT,
        soap TEXT,
        service_codes TEXT,
        rejection_reason TEXT,
        suggestions TEXT,
        embedding BLOB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    return conn

DB_CONN = _init_db()
DB_CURSOR = DB_CONN.cursor()

# -------------------------------
# FAISS setup - FIXED to use L2 distance instead of Inner Product
# -------------------------------
def _init_faiss_index():
    """Initializes the FAISS index, loading from file if it exists."""
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    if os.path.exists(INDEX_PATH):
        try:
            index = faiss.read_index(INDEX_PATH)
            logging.info(f"Loaded FAISS index with {index.ntotal} vectors from file.")
        except Exception as e:
            logging.error(f"Error loading FAISS index: {e}. Creating new index.")
            index = None
    else:
        index = None

    if index is None:
        sample = embed_model.encode(["test"], convert_to_numpy=True)
        dim = sample.shape[1]
        # FIXED: Use L2 distance instead of Inner Product for normalized similarity
        base_index = faiss.IndexFlatL2(dim)  # L2 distance
        index = faiss.IndexIDMap(base_index)
        faiss.write_index(index, INDEX_PATH)
        logging.info("Created new FAISS L2 index.")
    return index

FAISS_INDEX = _init_faiss_index()

# -------------------------------
# Helper function to normalize embeddings
# -------------------------------
def _normalize_embeddings(embeddings):
    """Normalize embeddings to unit length for proper cosine similarity"""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    # Avoid division by zero
    norms[norms == 0] = 1
    return embeddings / norms

# -------------------------------
# Suggestions extractor
# -------------------------------
def _extract_suggestions(analysis: Any) -> List[str]:
    suggestions = []
    results = getattr(analysis, 'results', None)
    if isinstance(results, CheckNoteResponse):
        results = results.dict().get('results', [])
    elif not isinstance(results, list):
        results = []

    for item in results:
        item_dict = item.dict() if isinstance(item, PerCodeResult) else item
        missing_terms = item_dict.get('missing_terms')
        if isinstance(missing_terms, list):
            for term in missing_terms:
                suggestions.append(f"Add '{term}'")

        rule_suggestions = item_dict.get('suggestions')
        if isinstance(rule_suggestions, list):
            suggestions.extend(rule_suggestions)

    final_suggestions = list(dict.fromkeys(suggestions))
    return final_suggestions

# -------------------------------
# Learning function - FIXED with normalized embeddings
# -------------------------------
def learn_from_rejection(req: ClaimRejectionRequest) -> ClaimRejectionResponse:
    """Adds a new failed claim to the knowledge base."""
    entities = analyze_text(req.soap)
    anon_soap = anonymize_text(req.soap, entities)

    # Generate and normalize embedding
    embedding = embed_model.encode([anon_soap], convert_to_numpy=True).astype(np.float32)
    normalized_embedding = _normalize_embeddings(embedding)
    emb_vector = normalized_embedding[0]

    # Step 1: Insert into the DB first to get the row ID
    DB_CURSOR.execute(
        """
        INSERT INTO claim_learning (claim_id, soap, service_codes, rejection_reason, suggestions, embedding)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            req.claim_id,
            anon_soap,
            ",".join(req.service_codes),
            req.rejection_reason,
            "[]",
            emb_vector.tobytes()
        )
    )
    DB_CONN.commit()
    row_id = DB_CURSOR.lastrowid
    logging.info(f"Inserted claim {req.claim_id} into DB with row_id: {row_id}")

    # Step 2: Add to FAISS index with the DB row ID as the label
    FAISS_INDEX.add_with_ids(normalized_embedding, np.array([row_id]))
    faiss.write_index(FAISS_INDEX, INDEX_PATH)
    logging.info(f"Added vector to FAISS index with ID: {row_id}. Total vectors: {FAISS_INDEX.ntotal}")

    # Step 3: Update suggestions and the faiss_id in the DB
    analysis_dict = validate_soap_against_codes(req.soap, req.service_codes)
    analysis_obj = CheckNoteResponse(**analysis_dict)
    suggestions = _extract_suggestions(analysis_obj)
    DB_CURSOR.execute("UPDATE claim_learning SET suggestions=?, faiss_id=? WHERE id=?", (json.dumps(suggestions), row_id, row_id))
    DB_CONN.commit()
    logging.info(f"Updated suggestions for row_id {row_id}")

    return ClaimRejectionResponse(analysis=analysis_dict, suggestions=suggestions)

# ----------------------------------------------------------------------------
# Prediction lookup function - FIXED with L2 distance conversion
# ----------------------------------------------------------------------------
def lookup_learned_failure(soap: str, service_codes: List[str]) -> Dict[str, Any] | None:
    """
    Looks up similar failures using the FAISS index and returns matching suggestions.
    """
    if FAISS_INDEX.ntotal == 0:
        logging.info("FAISS index is empty. No learned failures to look up.")
        return None

    entities = analyze_text(soap)
    anon_soap = anonymize_text(soap, entities)

    # Generate and normalize query embedding
    embedding = embed_model.encode([anon_soap], convert_to_numpy=True).astype(np.float32)
    normalized_embedding = _normalize_embeddings(embedding)

    # Perform search. With L2 distance, smaller values = more similar
    D, I = FAISS_INDEX.search(normalized_embedding, TOP_K_SIMILAR)

    l2_distance = float(D[0][0])
    row_id = int(I[0][0])

    # Convert L2 distance to similarity score (0-1, where 1 = identical)
    # For normalized vectors, L2 distance ranges from 0 to 2
    similarity_score = max(0, 1 - (l2_distance / 2))

    logging.info(f"FAISS search found ID {row_id} with L2 distance {l2_distance:.3f}, similarity {similarity_score:.3f}.")

    if similarity_score < SIM_THRESHOLD:
        logging.info(f"Similarity {similarity_score:.3f} is below threshold {SIM_THRESHOLD}. No match found.")
        return None

    # Use the retrieved row_id to directly query the database
    DB_CURSOR.execute("SELECT service_codes, suggestions FROM claim_learning WHERE id=?", (row_id,))
    row = DB_CURSOR.fetchone()
    if not row:
        logging.error(f"DB row with id {row_id} not found. This should not happen.")
        return None

    stored_codes_str, stored_suggestions_json = row
    stored_codes = stored_codes_str.split(",")

    if sorted(stored_codes) == sorted(service_codes):
        logging.info(f"Matching service codes found: {stored_codes}")
        if stored_suggestions_json:
            try:
                suggestions = json.loads(stored_suggestions_json)
                return {"suggestions": suggestions}
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode JSON from DB for suggestions: {stored_suggestions_json}. Error: {e}")
                return {"suggestions": []}
        else:
            logging.warning("Suggestions JSON from DB is empty.")
            return {"suggestions": []}

    logging.info(f"Service codes do not match. Stored: {stored_codes}, Provided: {service_codes}")
    return None

def reset_learning_index_storage():
    """Safely resets the DB and FAISS index files."""
    global FAISS_INDEX, DB_CONN, DB_CURSOR
    try:
        if DB_CONN:
            DB_CONN.close()
    except Exception:
        pass
    for path in [DB_PATH, INDEX_PATH]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except PermissionError:
                import time
                time.sleep(0.1)
                os.remove(path)
    DB_CONN = _init_db()
    DB_CURSOR = DB_CONN.cursor()
    FAISS_INDEX = _init_faiss_index()
    logging.info("Learning index and storage have been reset.")