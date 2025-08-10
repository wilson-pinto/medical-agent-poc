import os
import argparse
import xml.etree.ElementTree as ET
import sqlite3
import faiss
import numpy as np
from app.core.sentence_model_registry import get_sentence_model

# --------- Config ---------
XML_FILE = "data/taksttabell.xml"
DB_FILE = "data/codes.db"
FAISS_INDEX_FILE = "index/codes_index.faiss"
EMBED_MODEL = "NbAiLab/nb-sbert-base"
NAMESPACE = {"ns": "http://helfo.no/skjema/taksttabell"}
# --------------------------

def load_codes_from_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    takster = root.findall("ns:Takst", NAMESPACE)

    codes = []
    for takst in takster:
        code_id = takst.find("ns:takstkode", NAMESPACE).text.strip()
        description = takst.find("ns:Beskrivelse", NAMESPACE).text.strip()
        codes.append((code_id, description))

    return codes

def save_to_sqlite(codes):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS codes")
    cur.execute("CREATE TABLE codes (id TEXT, description TEXT)")
    cur.executemany("INSERT INTO codes VALUES (?, ?)", codes)
    conn.commit()
    conn.close()

def build_faiss_index(codes, model_name):
    model = get_sentence_model(model_name)
    descriptions = [desc for _, desc in codes]
    embeddings = model.encode(descriptions, convert_to_numpy=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, FAISS_INDEX_FILE)
    print(f"FAISS index with {len(codes)} codes saved to {FAISS_INDEX_FILE}")

def verify_index():
    if not os.path.exists(DB_FILE) or not os.path.exists(FAISS_INDEX_FILE):
        print("[ERROR] Missing DB or FAISS index file.")
        return False

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM codes")
    db_count = cur.fetchone()[0]
    conn.close()

    index = faiss.read_index(FAISS_INDEX_FILE)
    faiss_count = index.ntotal

    if db_count != faiss_count:
        print(f"[FAIL] Mismatch: DB has {db_count} codes, FAISS has {faiss_count} embeddings.")
        return False

    print(f"[PASS] DB and FAISS index match: {db_count} codes.")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="Verify DB ↔ FAISS consistency")
    args = parser.parse_args()

    if args.verify:
        verify_index()
        return

    if not os.path.exists(XML_FILE):
        print(f"Missing XML file at {XML_FILE}")
        return

    print("Loading codes from XML...")
    codes = load_codes_from_xml(XML_FILE)
    print(f"Loaded {len(codes)} codes")

    print("Saving to SQLite...")
    save_to_sqlite(codes)
    print(f"Saved to {DB_FILE}")

    print("Generating embeddings + saving FAISS index...")
    build_faiss_index(codes, EMBED_MODEL)
    print("All done!")

if __name__ == "__main__":
    main()
