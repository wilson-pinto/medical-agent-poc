# scripts/build_english_service_code_db_and_index.py

import sqlite3
import faiss
import numpy as np
import xml.etree.ElementTree as ET
from sentence_transformers import SentenceTransformer
from pathlib import Path

# ---------------- Config ----------------
XML_FILE = "data/taksttabell.xml"
DB_FILE = "data/service_codes.db"
INDEX_FILE = "index/service_codes_index.faiss"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5

Path("data").mkdir(exist_ok=True)
Path("index").mkdir(exist_ok=True)

# ---------------- Parse XML ----------------
tree = ET.parse(XML_FILE)
root = tree.getroot()

namespace = {"ns": "http://helfo.no/skjema/taksttabell"}
codes = []

for takst in root.findall("ns:Takst", namespace):
    code = takst.find("ns:takstkode", namespace).text
    description = takst.find("ns:beskrivelse", namespace).text
    codes.append((code, description))

print(f"Parsed {len(codes)} service codes from {XML_FILE}")

# ---------------- Create SQLite DB ----------------
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS service_codes (
    id TEXT PRIMARY KEY,
    description TEXT
)
""")
cursor.execute("DELETE FROM service_codes")  # clear old data
cursor.executemany("INSERT INTO service_codes (id, description) VALUES (?, ?)", codes)
conn.commit()
conn.close()
print(f"Saved {len(codes)} service codes to {DB_FILE}")

# ---------------- Create FAISS Index ----------------
model = SentenceTransformer(EMBED_MODEL)

descriptions = [desc for _, desc in codes]
embeddings = model.encode(descriptions, convert_to_numpy=True)
embeddings = embeddings.astype(np.float32)

# Normalize embeddings
faiss.normalize_L2(embeddings)

index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)
faiss.write_index(index, INDEX_FILE)
print(f"FAISS index saved to {INDEX_FILE}, total vectors: {index.ntotal}")
