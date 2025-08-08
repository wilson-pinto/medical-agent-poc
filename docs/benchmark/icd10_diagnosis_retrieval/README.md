# 📊 Benchmark: ICD-10 Code Retrieval from SOAP Notes

This benchmark evaluates which sentence embedding model best retrieves the correct **ICD-10 diagnosis code** from clinical notes (SOAP format). This is a key task for our AI assistant in Norwegian healthcare.

---

## 🧪 What We Tested

We compared **4 embedding models** for their ability to:
- Understand free-text SOAP notes (English & Norwegian)
- Match the correct ICD-10 diagnosis code
- Rank the correct code in the top 5 most similar codes

---

## 🗂️ Dataset

- **`soap_eval_data.csv`**: 40 clinical notes with expected ICD-10 codes (20 English, 20 Norwegian)
- **`icd10_norway.xlsx`**: Official ICD-10 codes and descriptions

Each SOAP entry example:
```csv
patient_id,soap,expected_codes,lang
1,"Typhoid fever diagnosed recently",A010,ENG
```

---

## 🤖 Models Tested

| Model                          | Size   | Domain               |
|-------------------------------|--------|----------------------|
| NbAiLab/nb-sbert-base         | Medium | Norwegian            |
| abhinand/MedEmbed-large-v0.1  | Large  | Medical              |
| all-MiniLM-L6-v2              | Small  | General-purpose      |
| vesteinn/ScandiBERT           | Medium | Nordic languages     |

---

## 📈 Evaluation Metrics

| Metric        | Description                                                                |
|---------------|----------------------------------------------------------------------------|
| **Recall@5**  | How often the correct code was in the top 5 results suggested.             |
| **MRR@5**     | How high the correct code was ranked among the top 5 (closer to 1 = best). |

**Key Metric Intuition:**
- **Recall@5**: Did the correct code appear in the top 5? (Higher = more reliable)
- **MRR@5**: Was the correct code near the top? (Closer to 1 = better ranking)

---

## 🥇 Results Summary

| Model                          | ENG R@5 | ENG MRR | NO R@5 | NO MRR | Overall R@5 | Overall MRR |
|-------------------------------|---------|---------|--------|--------|--------------|--------------|
| NbAiLab/nb-sbert-base         | 0.65    | 0.588   | 0.85   | 0.80   | 0.75         | 0.694        |
| abhinand/MedEmbed-large-v0.1  | 0.65    | 0.613   | 0.75   | 0.725  | 0.70         | 0.669        |
| all-MiniLM-L6-v2              | 0.60    | 0.446   | 0.65   | 0.60   | 0.625        | 0.523        |
| vesteinn/ScandiBERT           | 0.30    | 0.30    | 0.50   | 0.42   | 0.40         | 0.36         |

---

## 📖 Column Definitions

| Term            | Meaning                                                                 |
|-----------------|-------------------------------------------------------------------------|
| **ENG R@5**      | English notes: correct code in top 5 suggestions.                      |
| **ENG MRR**      | English notes: how high the correct code was ranked (1st = perfect).   |
| **NO R@5**       | Norwegian notes: correct code in top 5 suggestions.                    |
| **NO MRR**       | Norwegian notes: how high the correct code was ranked.                 |
| **Overall R@5**  | Average of English + Norwegian R@5.                                    |
| **Overall MRR**  | Average of English + Norwegian MRR.                                    |

---

## ✅ Key Findings

- 🏆 **NbAiLab/nb-sbert-base**: Best overall, especially strong in Norwegian.
- 🧠 **abhinand/MedEmbed-large-v0.1**: Strong in English, built for medical data.
- ⚖️ **all-MiniLM-L6-v2**: Small, fast; good fallback if speed is critical.
- ❌ **vesteinn/ScandiBERT**: Performed poorly; not recommended for this use case.

---
