# app/core/claim_learning_engine.py
import os
import json
import sqlite3
import faiss
import numpy as np
from typing import List, Dict, Any

from app.core.pii_analyzer import analyze_text, anonymize_text
from app.core.sentence_model_registry import get_sentence_model
from app.core.validate_note_requirements.engine import validate_soap_against_codes
from app.schemas import ClaimRejectionRequest, ClaimRejectionResponse
from app.schemas_new.validate_note_requirements import CheckNoteResponse, PerCodeResult


# -------------------------------
# CONFIG
# -------------------------------
EMBED_MODEL = "NbAiLab/nb-sbert-base"
DB_PATH = "data/claim_learning.db"
INDEX_PATH = "index/claim_learning.faiss"
TOP_K_SIMILAR = 1
SIM_THRESHOLD = 0.75

# -------------------------------
# Load embedding model
# -------------------------------
embed_model = get_sentence_model(EMBED_MODEL)

# -------------------------------
# SQLite setup (auto-create)
# -------------------------------
def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claim_learning (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
# FAISS setup  (auto-create)
# -------------------------------
def _init_faiss_index():
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    if os.path.exists(INDEX_PATH):
        index = faiss.read_index(INDEX_PATH)
    else:
        sample = embed_model.encode(["test"], convert_to_numpy=True)
        dim = sample.shape[1]
        index = faiss.IndexFlatIP(dim)
        faiss.write_index(index, INDEX_PATH)
    return index

FAISS_INDEX = _init_faiss_index()

# -------------------------------
# Suggestions extractor (FIXED)
# -------------------------------
def _extract_suggestions(analysis: Any) -> List[str]:
    import logging
    logging.basicConfig(level=logging.INFO)

    suggestions = []

    logging.info(f"Starting _extract_suggestions with analysis object: {type(analysis)}")

    # Safely get the results list, converting to a list of dicts if needed
    results = getattr(analysis, 'results', None)
    if isinstance(results, CheckNoteResponse):
        results = results.dict().get('results', [])
    elif not isinstance(results, list):
        results = []

    logging.info(f"Analysis has {len(results)} results.")
    for item in results:
        # Ensure item is a dictionary to use .get()
        item_dict = item.dict() if isinstance(item, PerCodeResult) else item
        logging.info(f"Processing result for service code: {item_dict.get('service_code', 'N/A')}")

        # Check for missing_terms
        missing_terms = item_dict.get('missing_terms')
        if isinstance(missing_terms, list):
            logging.info(f"Found missing terms: {missing_terms}")
            for term in missing_terms:
                suggestions.append(f"Add '{term}'")

        # Check for rule suggestions
        rule_suggestions = item_dict.get('suggestions')
        if isinstance(rule_suggestions, list):
            logging.info(f"Found rule suggestions: {rule_suggestions}")
            suggestions.extend(rule_suggestions)

    # Remove duplicates
    final_suggestions = list(dict.fromkeys(suggestions))
    logging.info(f"Final suggestions: {final_suggestions}")

    return final_suggestions

def learn_from_rejection(req: ClaimRejectionRequest) -> ClaimRejectionResponse:
    entities = analyze_text(req.soap)
    anon_soap = anonymize_text(req.soap, entities)
    embedding = embed_model.encode([anon_soap], convert_to_numpy=True).astype(np.float32)
    emb_vector = embedding[0]

    FAISS_INDEX.add(embedding)
    faiss.write_index(FAISS_INDEX, INDEX_PATH)

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
            "",
            emb_vector.tobytes()
        )
    )
    DB_CONN.commit()
    row_id = DB_CURSOR.lastrowid

    analysis_dict = validate_soap_against_codes(req.soap, req.service_codes)
    analysis_obj = CheckNoteResponse(**analysis_dict)

    suggestions = _extract_suggestions(analysis_obj)

    DB_CURSOR.execute("UPDATE claim_learning SET suggestions=? WHERE id=?", (json.dumps(suggestions), row_id))
    DB_CONN.commit()

    return ClaimRejectionResponse(analysis=analysis_dict, suggestions=suggestions)

# ----------------------------------------------------------------------------
# OVERRIDE CHECK
# ----------------------------------------------------------------------------
def lookup_learned_failure(soap: str, service_codes: List[str]) -> Dict[str, Any] | None:
    if FAISS_INDEX.ntotal == 0:
        return None

    entities = analyze_text(soap)
    anon_soap = anonymize_text(soap, entities)
    embedding = embed_model.encode([anon_soap], convert_to_numpy=True).astype(np.float32)
    D, I = FAISS_INDEX.search(embedding, TOP_K_SIMILAR)

    score = float(D[0][0])
    idx = int(I[0][0])

    if score < SIM_THRESHOLD:
        return None

    # Safe fetch: map FAISS index to SQLite row by order of insertion
    DB_CURSOR.execute("SELECT id, service_codes, suggestions FROM claim_learning ORDER BY id ASC LIMIT 1 OFFSET ?", (idx,))
    row = DB_CURSOR.fetchone()
    if not row:
        return None

    _, stored_codes_str, stored_suggestions_json = row
    stored_codes = stored_codes_str.split(",")

    if sorted(stored_codes) == sorted(service_codes):
        # FIX: Check for a valid JSON string before attempting to load
        if stored_suggestions_json:
            try:
                # Use a specific exception for JSON decoding errors
                return {"suggestions": json.loads(stored_suggestions_json)}
            except json.JSONDecodeError:
                # Log the error for debugging and return an empty list
                import logging
                logging.error(f"Failed to decode JSON from DB for suggestions: {stored_suggestions_json}")
                return {"suggestions": []}
        else:
            # Handle cases where the JSON string is empty or None
            return {"suggestions": []}

    return None

def reset_learning_index_storage():
    global FAISS_INDEX, DB_CONN, DB_CURSOR

    # Close DB connection before removing
    try:
        if DB_CONN:
            DB_CONN.close()
    except Exception:
        pass

    # Remove files safely
    for path in [DB_PATH, INDEX_PATH]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except PermissionError:
                import time
                time.sleep(0.1)
                os.remove(path)

    # Re-initialize
    DB_CONN = _init_db()
    DB_CURSOR = DB_CONN.cursor()
    FAISS_INDEX = _init_faiss_index()