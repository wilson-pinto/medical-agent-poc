# Improving ICD-10 Norway Diagnosis Code Matching Accuracy

---

## 🔍 What We Did

We wanted to accurately match ICD-10 Norway diagnosis codes using AI models. But at first, the results weren't very good.

So we followed a simple process:

1. **Created our own test cases** for matching.
2. **Tried a few different models** to see which ones worked better.
3. **Improved the input formatting** using Gemini (we call this "refactoring").
4. **Added a cross-encoder** to re-rank the top results and improve accuracy.

---

## 🧪 Step-by-Step Journey

### ✅ Step 1: Tried Embedding Models (Before Input Refactoring)

- **Recall@5** was around **23–28%**
- Not very good — we were missing most of the correct diagnoses.

### ✅ Step 2: Added Cross-Encoders (Before Refactoring)

- Accuracy improved to **40% Recall@5** with the best model combo.
- Still not ideal, but better.

### ✅ Step 3: Refactored Inputs Using Gemini

- Suddenly, big improvement!
- One model (NbAiLab) jumped from **23% to 76% Recall@5** just by cleaning up the input.
- Shows how important input formatting is!

### ✅ Step 4: Combined Everything — Refactored Input + Cross-Encoder

- This gave us the **best performance overall**:
  - **Recall@5: 80%**
  - **MRR@5: 71.3%**
- The final model:  
  `NbAiLab/nb-sbert-base + mmarco-mMiniLMv2-L12-H384-v1`

---

## 🔢 What These Metrics Mean

- **Recall@5**: Out of the top 5 suggestions, how often did we get the correct one?
- **MRR@5**: Did the correct answer show up near the top of the list?

Higher = Better 👍

---

## 🚀 Final Recommendation

If you're working on diagnosis code matching for ICD-10 Norway:

> 🏆 Use the **NbAiLab + mmarco cross-encoder** with **Gemini-refactored input**.

You'll get the most accurate results — with **80%** of the correct answers appearing in the top 5 suggestions.

---

## 📊 Quick Comparison Table

| Scenario                    | Best Model Combo                                 | Recall@5 | MRR@5 |
|-----------------------------|--------------------------------------------------|----------|--------|
| 1. Embed before refactoring | all-MiniLM-L6-v2                                 | 0.280    | 0.209  |
| 2. + Cross-encoder          | all-MiniLM + ms-marco                            | 0.400    | 0.345  |
| 3. Refactored input only    | NbAiLab                                          | 0.760    | 0.636  |
| 4. Everything combined      | **NbAiLab + mmarco (refactored input)**          | **0.800**| **0.713** |

---

## 🎯 Summary

We started with low accuracy.  
We improved step-by-step: better models, cleaner inputs, and smarter re-ranking.  
Now we have a setup that works great.

Simple changes. Big impact.

---
