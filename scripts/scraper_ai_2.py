import os
import requests
from bs4 import BeautifulSoup
import re
import yaml
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

helfo_url = 'https://www.helfo.no/lege/Regelverk-og-takster-for-lege/ofte-brukte-takstar-for-legar'

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Set the GEMINI_API_KEY environment variable")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")



def strip_code_fences(text):
    return re.sub(r'^```yaml\s*|```$', '', text.strip(), flags=re.MULTILINE).strip()


def scrape_helfo_fee_codes(url):
    print("Fetching page...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, 'html.parser')

    fee_codes = {}
    headings = soup.find_all(['h2', 'h3', 'h4'])

    i = 0
    while i < len(headings):
        h = headings[i]
        if is_fee_code_heading(h):
            fee_code = extract_fee_code(h.get_text())
            if not fee_code:
                i += 1
                continue

            main_section = find_main_section_for_tag(h) or ""

            content = {"Forskriftstekst": "", "Forklaring": "", "Eksempel": ""}

            j = i + 1
            current_subsection = None

            while j < len(headings) and not is_fee_code_heading(headings[j]) and not (headings[j].name == 'h2'):
                sub_tag = headings[j]
                sub_text = sub_tag.get_text(strip=True).lower()

                if 'forskriftstekst' in sub_text:
                    current_subsection = "Forskriftstekst"
                    content[current_subsection] = ""
                elif 'forklaring' in sub_text:
                    current_subsection = "Forklaring"
                    content[current_subsection] = ""
                elif 'eksempel' in sub_text:
                    current_subsection = "Eksempel"
                    content[current_subsection] = ""
                else:
                    if current_subsection:
                        p = sub_tag.find_next_sibling()
                        texts = []
                        while p and p.name not in ['h2', 'h3', 'h4']:
                            if p.name in ['p', 'ul', 'ol']:
                                texts.append(p.get_text(separator="\n", strip=True))
                            p = p.find_next_sibling()
                        if texts:
                            content[current_subsection] += "\n".join(texts)
                        current_subsection = None
                        j += 1
                        continue
                j += 1

            fee_codes[fee_code] = {
                "main_section": main_section,
                "Forskriftstekst": content["Forskriftstekst"].strip(),
                "Forklaring": content["Forklaring"].strip(),
                "Eksempel": content["Eksempel"].strip(),
            }
            i = j
        else:
            i += 1

    print(f"Extracted {len(fee_codes)} fee codes.")
    return fee_codes

def is_fee_code_heading(tag):
    if tag.name in ['h3', 'h4', 'h2']:
        text = tag.get_text(strip=True)
        if re.search(r'Takst\s+\w+', text):
            return True
    return False

def extract_fee_code(text):
    match = re.search(r'Takst\s+(\w+)', text)
    return match.group(1) if match else None

def find_main_section_for_tag(tag):
    previous = tag.find_all_previous('h2')
    if previous:
        return previous[0].get_text(strip=True)
    return None

def generate_structured_yaml_with_gemini(fee_code, content_dict):
    prompt = f"""
Extract the following fields as YAML for the HELFO takst code "{fee_code}":

- name: a short descriptive name (Norwegian)
- required_terms: list of terms required in documentation (list of Norwegian keywords)
- warn_terms: list of terms that if missing should trigger a warning
- suggestions: user suggestions to improve documentation quality
- version: always "HELFO-2025-01"
- requirement: a short text summarizing the official requirement (use the Forskriftstekst)
- severity:
    fail: failure message if required_terms missing
    warn: warning message if warn_terms missing

Content to analyze:
Forskriftstekst:
{content_dict['Forskriftstekst']}

Forklaring:
{content_dict['Forklaring']}

Eksempel:
{content_dict['Eksempel']}

Please respond with only YAML (no explanations).
"""

    response = model.generate_content(prompt)
    # Access the actual text inside the protobuf structure
    yaml_text = response.candidates[0].content.parts[0].text.strip()
    return yaml_text


if __name__ == "__main__":
    print("Starting scrape...")
    scraped_fee_codes = scrape_helfo_fee_codes(helfo_url)

    if not scraped_fee_codes:
        print("No fee codes extracted, exiting.")
        exit(1)

    final_structured = {}

    for code, content in scraped_fee_codes.items():
        print(f"Processing code {code} with Gemini LLM...")
        try:
            yaml_text = generate_structured_yaml_with_gemini(code, content)
            yaml_text = strip_code_fences(yaml_text)
            data = yaml.safe_load(yaml_text)
            final_structured[code] = data
        except Exception as e:
            print(f"Failed to process {code}: {e}")

    with open("helfo_fee_codes_structured.yaml", "w", encoding="utf-8") as f:
        yaml.dump(final_structured, f, allow_unicode=True, sort_keys=False)

    print(f"Structured data saved to helfo_fee_codes_structured.yaml")
