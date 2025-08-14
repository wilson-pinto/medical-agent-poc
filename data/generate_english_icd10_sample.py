import pandas as pd

# Sample data (first 20 rows translated)
data = [
    ["A000", "Cholera due to Vibrio cholerae 01, biovar cholerae", "Cholera due to Vibrio cholerae 01, biovar cholerae", "", "", "", ""],
    ["A001", "Cholera due to Vibrio cholerae 01, biovar eltor", "Cholera due to Vibrio cholerae 01, biovar eltor", "", "", "", ""],
    ["A009", "Cholera, unspecified", "Cholera, unspecified", "", "", "", "X"],
    ["A010", "Typhoid fever", "Typhoid fever", "", "", "", ""],
    ["A011", "Paratyphoid fever A", "Paratyphoid fever A", "", "", "", ""],
    ["A012", "Paratyphoid fever B", "Paratyphoid fever B", "", "", "", ""],
    ["A013", "Paratyphoid fever C", "Paratyphoid fever C", "", "", "", ""],
    ["A014", "Paratyphoid fever, unspecified", "Paratyphoid fever, unspecified", "", "", "", "X"],
    ["A020", "Salmonella enteritis", "Salmonella enteritis", "", "", "", ""],
    ["A021", "Salmonella sepsis", "Salmonella sepsis", "", "", "", ""],
    ["A022", "Localized salmonella infection", "Localized salmonella infection", "", "", "", ""],
    ["A028", "Other specified salmonella infection", "Other specified salmonella infection", "", "", "", ""],
    ["A029", "Salmonella infection, unspecified", "Salmonella infection, unspecified", "", "", "", "X"],
    ["A030", "Shigellosis due to Shigella dysenteriae", "Shigellosis due to Shigella dysenteriae", "", "", "", ""],
    ["A031", "Shigellosis due to Shigella flexneri", "Shigellosis due to Shigella flexneri", "", "", "", ""],
    ["A032", "Shigellosis due to Shigella boydii", "Shigellosis due to Shigella boydii", "", "", "", ""],
    ["A033", "Shigellosis due to Shigella sonnei", "Shigellosis due to Shigella sonnei", "", "", "", ""],
    ["A038", "Other specified shigellosis", "Other specified shigellosis", "", "", "", ""],
    ["A039", "Shigellosis, unspecified", "Shigellosis, unspecified", "", "", "", "X"],
    ["A040", "Enteropathogenic E. coli infection", "Enteropathogenic E. coli infection", "", "", "", ""]
]

columns = [
    "Code",
    "Full Description (No Length Limit)",
    "Description (Max 60 characters)",
    "Star Code",
    "Modifier Code (never first)",
    "Gender-specific (M/F)",
    "Non-specific Code"
]

df = pd.DataFrame(data, columns=columns)

# Save as Excel
df.to_excel("ICD10_English_Sample.xlsx", index=False)
print("Excel file saved as ICD10_English_Sample.xlsx")
