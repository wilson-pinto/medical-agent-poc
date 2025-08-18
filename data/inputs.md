# AI Check Note Requirements

## PASS Scene
```json
{
  "soap": "The patient came in with a fever. Temperature measurement showed 38.5°C. Advice was given regarding rest, fluid intake, and pain-relieving medications. Further follow-up of chronic disease included a medical evaluation, a treatment plan with medication adjustments, and lifestyle advice. For heart surgery, a full preoperative consultation was conducted, including risk assessment, ECG, blood tests, and patient information about the procedure.",
  "service_codes":["2fev","4chr","3hrt"]
}

````

## WARN Scene

```json
{
  "soap": "The patient presented with signs of fever and was advised on hydration and the use of pain relievers. A general assessment was done. Although the fever was discussed, no exact temperature value was recorded. Follow-up for chronic disease included a medical evaluation and treatment plan. Preoperative assessment for heart surgery was conducted with risk evaluation, ECG, and blood tests.",
  "service_codes": ["2fev", "4chr", "3hrt"]
}

```

## FAIL Scene

```json
{
  "soap": "The patient came in with a fever. Temperature measurement was performed, and advice was given regarding hydration and the use of pain relievers. Regarding chronic disease, a follow-up was conducted where a medical evaluation was done, but the treatment plan was missing. For heart surgery, surgery and preoperative consultation were mentioned, but there was no risk assessment or details about tests such as ECG or blood samples.",
  "service_codes": ["2fev", "4chr", "3hrt"]
}
```

# Extract Diagnosis code

Patient admitted with severe diarrhea, vomiting, and dehydration. Recently returned from travel to Southeast Asia. Laboratory tests confirm Vibrio cholerae 01, biovar cholerae. Fluid and electrolyte replacement therapy initiated.

Toddler with watery diarrhea and vomiting for two days. Stool sample confirms enteropathogenic E. coli. Focus on fluid balance and electrolyte correction.

Male with diarrhea and abdominal pain. Parasitological examination suggests protozoal infection, but specific organism not identified.

Female with renal failure and systemic symptoms. Kidney biopsy confirms renal tuberculosis. Treatment adapted to reduced renal function started.

# Suggest Service codes:
