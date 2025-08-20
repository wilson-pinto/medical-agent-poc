# AI Alchemist – Clinical Coding Assistant
## 📘 Technical Documentation

---

## 1. Data Sources & Licensing

| Source                       | Usage                                    | License            |
|------------------------------|------------------------------------------|--------------------|
| [Helfo Official Website](https://www.helfo.no/) | Scraped publicly available documentation related to clinical procedures and ICD coding in Norway | Public (open web data) |
| `icd10_norway.xlsx`          | Official ICD-10 codebook & descriptions   | WHO ICD-10 License |
| `soap_eval_data.csv`         | Internally created evaluation dataset (40 SOAP clinical notes, 20 EN / 20 NO) | Proprietary / Internal use only |

---

## 2. Model Details

### 🔨 Retrieval Pipeline

| Component            | Model / Tool                                  | Purpose                             |
|---------------------|-----------------------------------------------|-------------------------------------|
| Sentence Encoder     | `NbAiLab/nb-sbert-base` (default)              | Embed cleaned SOAP text → vector space |
| FAISS Index         | HNSW-based Index                               | Fast vector similarity search over ICD codes |
| Cross-Encoder        | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`   | Re-rank top 50 retrieved codes for final ranking |

### 🧠 LLM (Gemini)

| Model       | Provider | Usage                                  |
|------------|----------|-----------------------------------------|
| `gemini-1.5-flash` | Google Generative AI | Pre-processing prompt: rewrite SOAP text into concise, medically-relevant embedding-friendly sentence |

**Hybrid Architecture Overview:**

1. 🧾 Raw SOAP → cleaned by Gemini.
2. ➡ Embedded (bi-encoder) → FAISS top-K retrieval.
3. 🔁 Ranked via Cross-Encoder → final code suggestion.

---

## 3. Evaluation Methodology & Results

### 🎯 Benchmark Task
**ICD-10 Code Retrieval from SOAP Clinical Notes (English & Norwegian)**

- Goal: Can the system retrieve the correct ICD-10 code within top 5 suggestions?
- Dataset: `soap_eval_data.csv` (40 notes: 20 EN, 20 NO)
- Metrics:
    - **Recall@5** — fraction of cases where correct code is in top 5
    - **MRR@5** — Mean Reciprocal Rank within top 5

### 🧪 Models Compared

| Model                          | Size   | Domain            |
|---------------------------------|--------|-------------------|
| NbAiLab/nb-sbert-base           | Medium | Norwegian         |
| abhinand/MedEmbed-large-v0.1    | Large  | Medical (EN)      |
| all-MiniLM-L6-v2               | Small  | General-purpose   |
| vesteinn/ScandiBERT            | Medium | Nordic languages  |

### 📊 Results Summary

| Model                          | ENG R@5 | ENG MRR | NO R@5 | NO MRR | Overall R@5 | Overall MRR |
|---------------------------------|--------|--------|--------|--------|-------------|-------------|
| NbAiLab/nb-sbert-base           | 0.65   | 0.588  | 0.85   | 0.80   | 0.75        | 0.694       |
| abhinand/MedEmbed-large-v0.1    | 0.65   | 0.613  | 0.75   | 0.725  | 0.70        | 0.669       |
| all-MiniLM-L6-v2               | 0.60   | 0.446  | 0.65   | 0.60   | 0.625       | 0.523       |
| vesteinn/ScandiBERT            | 0.30   | 0.30   | 0.50   | 0.42   | 0.40        | 0.36        |

**🏆 Winner:** `NbAiLab/nb-sbert-base` — best performance overall and particularly strong on Norwegian inputs.

---

## 4. Known Limitations

- Current embedding models are **not fine-tuned on Norwegian clinical-specific vocabulary**, leading to occasional mismatches on rare or domain-specific terms.
- Evaluation was done on a relatively **small internal dataset (n=40)**.
---

## 5. Improvement Areas & Future Work

- Fine-tune `nb-sbert-base` (or similar) **on Norwegian clinical notes**.
- Expand internal evaluation dataset (≥500 notes) for stronger statistical confidence.

---