# 🧠 Medical Billing Agent POC

A lightweight offline AI agent to help healthcare practitioners:

- ✅ Suggest accurate service codes from user input or SOAP notes
- 🚨 Validate claims before submission to reduce HELFO rejections

---

## 📌 Why This Is Needed

### AI for Suggesting Service Codes
- **Problem:** Practitioners struggle to pick correct codes from large, complex lists.
- **Impact:** Incorrect codes cause claim rejections and delays.
- **AI Advantage:** Instantly suggests relevant service codes using your input or notes.

### AI for Validating Claims
- **Problem:** Claims often get rejected due to wrong code combos or missing details.
- **Impact:** Wasted time on rework and resubmissions.
- **AI Advantage:** Pre-checks claims and flags potential issues before submission.

---

## 🛠️ Tech Stack

| Component            | Description                                 |
|---------------------|---------------------------------------------|
| FastAPI             | API framework for agents                    |
| FAISS               | Semantic search index for service codes     |
| SQLite              | Local DB for service and diagnosis codes    |
| SentenceTransformers| Embedding model for semantic search         |
| OpenAI GPT-4o       | For intelligent reranking                   |
| Gemini Pro/Flash    | Alternative reranking via Google AI         |

---

## 🧰 Prerequisites

1. Install [Anaconda (Miniconda)](https://docs.conda.io/en/latest/miniconda.html)
2. Python 3.10+ (bundled with Miniconda)

```bash
conda create -n medical-agent python=3.10 -y
conda activate medical-agent
```

---

## 📦 Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd medical-agent-poc
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

If you don’t have `requirements.txt`, run:

```bash
pip install fastapi uvicorn pydantic sentence-transformers openai faiss-cpu python-dotenv google-generativeai openpyxl pandas presidio-analyzer presidio-anonymizer
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...your-openai-key
GEMINI_API_KEY=your-gemini-key
GOOGLE_API_KEY=your-gemini-key
USE_GEMINI=true
```

---

## 🔧 Build Search Indexes (One-time setup)

```bash
set PYTHONPATH=.
python scripts/build_code_index.py
python scripts/build_diagnosis_index.py
```

> Ensure `data/taksttabell.xml` and `data/icd10_norway.xlsx` are present.

This creates:
- `data/codes.db`
- `data/diagnosis_codes.db`
- `index/codes_index.faiss`
- `index/diagnosis_index.faiss`

---

## 🚀 Running the App

```bash
uvicorn app.main:app --reload
```

Visit: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for Swagger UI.

---

## 📌 Endpoints

### `/agent/search/invoke` — Suggest service codes (semantic search)

**POST** `/agent/search/invoke`
```json
{
  "session_id": "test-001",
  "query": "øyekonsultasjon etter kirurgi",
  "top_k": 5
}
```

### `/agent/rerank/invoke` — Re-rank candidates using Gemini or GPT-4o

**POST** `/agent/rerank/invoke`
```json
{
  "session_id": "test-001",
  "query": "øyekonsultasjon etter kirurgi",
  "candidates": [
    "K01a: Kataraktoperasjon",
    "K01d: Operasjon av øyelokk",
    "H1: Blåreseptsøknad"
  ]
}
```

### `/ai/extract-diagnoses` — Extract ICD-10 codes from SOAP text

**POST** `/ai/extract-diagnoses`
```json
{
  "soap": "Pasienten har hatt feber og sår hals i 2 dager."
}
```

### `/ai/check-service-diagnosis` — Validate that diagnosis & note justify service codes

**POST** `/ai/check-service-diagnosis`
```json
{
  "soap": "Sår hals, CRP forhøyet. Fikk rekvirert antibiotika.",
  "diagnoses": ["J02"],
  "service_codes": ["212b"]
}
```

### `/ai/check-note-requirements` — Check if SOAP supports required documentation

**POST** `/ai/check-note-requirements`
```json
{
  "soap": "Sår hals, svelgvansker. Utført halsundersøkelse.",
  "service_codes": ["212b"]
}
```

### `/semantic-combo-warning` — Warn about rare or suspicious code combos

**POST** `/semantic-combo-warning`
```json
{
  "soap": "Rutinekontroll og samtidig akutt infeksjon.",
  "service_codes": ["1ae", "1ad"]
}
```

### `/diagnosis/search/invoke` — Search ICD-10 diagnosis semantically

**POST** `/diagnosis/search/invoke`
```json
{
  "query": "pasient har smerter i korsryggen",
  "top_k": 5
}
```

---

## 🧪 Sample Data

- `taksttabell.xml` – Source XML for service codes
- `icd10_norway.xlsx` – Diagnosis reference list

Update these and re-run build scripts as needed.

---

## 🔮 Future Features
- Auto-validate full XML claim forms
- Explain likely causes of HELFO rejections
- Fill missing fields from SOAP note context

---

## 👨‍💻 Maintainer
**Team AI Alchemists** — Built for HELFO claim quality improvements using AI
