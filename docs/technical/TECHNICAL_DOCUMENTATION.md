# AI Alchemist – Clinical Coding Assistant

## 📘 Technical Documentation (Updated)

---

## 1. Data Sources & Licensing

| Source                                                   | Usage                                                                | License                    |
| -------------------------------------------------------- | -------------------------------------------------------------------- | -------------------------- |
| [Helfo Official Website](https://www.helfo.no/)          | Public documentation on clinical procedures and ICD coding in Norway | Public (open web data)     |
| `icd10_english.xlsx`                                     | ICD-10 diagnosis codes and descriptions (Norwegian & English)        | WHO ICD-10 License         |
| `before_gemini_refactor.csv`, `gemini_refactor_soap.csv` | Internal evaluation datasets (EN SOAP notes, before/after Gemini)    | Proprietary / Internal use |

---

## 2. Model Pipeline Overview

### 🔁 Input Refactoring

| Component | Tool / Model       | Purpose                                                   |
| --------- | ------------------ | --------------------------------------------------------- |
| LLM       | `gemini-1.5-flash` | Refactors SOAP text → concise, medically focused sentence |

### 🧠 Embedding & Retrieval

| Component        | Model                   | Function                              |
| ---------------- | ----------------------- | ------------------------------------- |
| Sentence Encoder | `NbAiLab/nb-sbert-base` | Embed refactored input → vector space |
| FAISS Index      | HNSW-based FAISS        | Fast nearest-neighbor search          |

### 🎯 Re-Ranking (Cross-Encoder)

| Component     | Model                                        | Function                           |
| ------------- | -------------------------------------------- | ---------------------------------- |
| Cross-Encoder | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Re-rank top 50 ICD code candidates |

**Hybrid Pipeline Summary:**

1. 🧾 **Input:** Raw SOAP note
2. ✨ **Refactor via Gemini** (`gemini-1.5-flash`) → cleaner, embedding-friendly clinical sentence
3. 🔢 **Embed** with `nb-sbert-base` → vector embedding
4. 🔍 **Retrieve top-K** ICD-10 candidates via FAISS
5. 🧮 **Re-rank** using `mmarco-mMiniLMv2` cross-encoder → top-50 ICD codes
6. 🤖 **Final Selection via Gemini** → LLM is prompted with:
   * Refactored SOAP note
   * Top-ranked ICD-10 code list
     → Gemini selects **the most contextually appropriate ICD-10 code(s)**

---

## 3. Evaluation Methodology & Results

### 🎯 Benchmark Task

**ICD-10 Code Retrieval** from SOAP Notes (in English)

* Datasets:

  * `before_gemini_refactor.csv` (raw)
  * `gemini_refactor_soap.csv` (post-LLM refactoring)
* Metrics:

  * **Recall\@5** – How often the correct code is in top 5
  * **MRR\@5** – How highly ranked the correct code is (reciprocal rank)

---

## 4. Benchmarking Results (English SOAP Notes)

| Scenario                   | Pipeline                                      | Recall\@5 | MRR\@5    |
| -------------------------- | --------------------------------------------- | --------- | --------- |
| **Embed Only (Before)**    | `all-MiniLM-L6-v2`                            | 0.280     | 0.209     |
|                            | `NbAiLab/nb-sbert-base`                       | 0.230     | 0.110     |
| **Embed + Cross (Before)** | `all-MiniLM + ms-marco`                       | 0.400     | 0.345     |
|                            | `nb-sbert-base + ms-marco`                    | 0.370     | 0.287     |
| **Embed Only (After)**     | `NbAiLab/nb-sbert-base` (Post-Gemini)         | 0.760     | 0.636     |
|                            | `all-MiniLM-L6-v2` (Post-Gemini)              | 0.380     | 0.299     |
| **Embed + Cross (After)**  | `NbAiLab + mmarco-mMiniLMv2` (🔥 Recommended) | **0.800** | **0.713** |
|                            | `all-MiniLM + mmarco-mMiniLMv2`               | 0.470     | 0.430     |

**🏆 Best Overall:**
**`NbAiLab/nb-sbert-base` + `mmarco-mMiniLMv2-L12-H384-v1`**, with **Gemini-refactored input**, achieved **Recall\@5 = 0.800**, **MRR\@5 = 0.713**.

---

## 5. Known Limitations

* **Language Limitations:** All benchmarks were performed in **English**; Norwegian input still needs more empirical testing.
* **Limited Dataset:** Current evaluation was based on **small internal samples** (\~40-80 SOAP notes).
* **Cross-lingual Generalization:** Models not yet fine-tuned on **Norwegian clinical corpora**.
* **Input Quality Sensitivity:** Refactored inputs (via LLM) significantly improve performance; raw text yields poor retrieval.

---

## 6. Recommendations & Future Work

* ✅ **Use recommended pipeline**: `nb-sbert-base + mmarco-mMiniLMv2` + Gemini refactor.
* 🔁 **Expand dataset**: Scale to ≥500 multilingual SOAP notes.
* 🧠 **Fine-tune embeddings**: Adapt `nb-sbert-base` to **Norwegian medical data**.
* 🔬 **Evaluate in Norwegian**: Benchmark retrieval accuracy in real-world NO cases.
* 🔗 **Integrate UMLS / SNOMED CT mappings**: Enhance semantic coverage across diagnosis synonyms.

---
