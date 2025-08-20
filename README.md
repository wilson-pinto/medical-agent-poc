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
