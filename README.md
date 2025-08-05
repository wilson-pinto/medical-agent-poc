# 🧠 Medical Billing Agent POC

A lightweight offline AI agent designed to help healthcare practitioners:

1. ✅ Suggest accurate **service codes** based on user input or SOAP notes
2. 🚨 Validate **claims** before submission to reduce rejection from HELFO

---

## 📌 Why This Is Needed

### ✅ AI for Suggesting Service Codes
- **Problem**: Practitioners struggle to pick correct codes from large, complex lists.
- **Impact**: Incorrect codes cause claim rejections and delays.
- **AI Advantage**: Instantly suggests relevant service codes using your input or notes.

### 🚨 AI for Validating Claims
- **Problem**: Claims often get rejected due to wrong code combos or missing details.
- **Impact**: Wasted time on rework and resubmissions.
- **AI Advantage**: Pre-checks claims and flags potential issues before submission.

---

## 🛠️ Tech Stack

| Component          | Description                              |
|--------------------|------------------------------------------|
| `FastAPI`          | API framework for agents                 |
| `FAISS`            | Semantic search index for service codes |
| `SQLite`           | Local DB for service code metadata      |
| `SentenceTransformers` | Embedding model for semantic search |
| `OpenAI GPT-4o`    | For intelligent reranking               |

---

## 🧰 Prerequisites

1. **Install [Anaconda (Miniconda)](https://docs.conda.io/en/latest/miniconda.html)**
2. **Install Python 3.10+**
    - Already bundled with Miniconda
3. **Create and activate virtual env:**

```bash
conda create -n medical-agent python=3.10 -y
conda activate medical-agent
📦 Setup Instructions
Clone the Repo:

bash

git clone <your-repo-url>
cd medical-agent-poc
Install Dependencies:

bash

pip install -r requirements.txt
If you don’t have requirements.txt, here's the list to use:

bash

pip install fastapi uvicorn sentence-transformers openai faiss-cpu sqlite-utils python-dotenv
Get an OpenAI API Key:

Go to https://platform.openai.com/account/api-keys

Copy your key

Set Environment Variable (Windows):

bash

set OPENAI_API_KEY=sk-...your-key
You can also save it in a .env file:

bash

OPENAI_API_KEY=sk-...your-key
🗂️ Project Structure
graphql

medical-agent-poc/
├── data/
│   └── codes.db             # SQLite DB with service codes
├── index/
│   └── codes_index.faiss    # FAISS index for semantic search
├── taksttabell.xml          # Raw XML service codes
├── main.py                  # FastAPI app
├── README.md                # You are here
🚀 Running the App
Activate your conda env:

bash

conda activate medical-agent
Start the server:

bash

uvicorn main:app --reload
Open browser or use Postman to test:

📌 Endpoints
🔍 /agent/search/invoke — Suggest codes (semantic search)
json

POST http://127.0.0.1:8000/agent/search/invoke
{
  "session_id": "test-001",
  "query": "eye surgery consultation",
  "top_k": 5
}
🧠 /agent/rerank/invoke — Re-rank using GPT-4o
json

POST http://127.0.0.1:8000/agent/rerank/invoke
{
  "session_id": "test-001",
  "query": "eye surgery consultation",
  "candidates": ["K01a: Cataract surgery", "K01d: Eyelid surgery", "H1: Blåresept application"]
}
✅ /agent/formatter/invoke — Final result formatter
http

GET http://127.0.0.1:8000/agent/formatter/invoke?session_id=test-001&result=K01a
🧪 Sample Data
taksttabell.xml – Source XML file for service codes.

You can modify it and re-run the index generation script (to be added).

🔮 Future Features
Auto-validate claim forms using XML + journal notes

Explain reasons for likely rejection

Auto-fill missing fields using context

👨‍💻 Maintainer
Team AI Alchemists