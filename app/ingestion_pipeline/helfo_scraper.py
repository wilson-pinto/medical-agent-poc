import requests
from bs4 import BeautifulSoup
import re
import yaml
import google.generativeai as genai
import os

def _is_fee_code_heading(tag):
    """Checks if a BeautifulSoup tag is a fee code heading."""
    if tag and tag.name in ['h2', 'h3', 'h4']:
        text = tag.get_text(strip=True)
        if re.search(r'Takst\s+\w+', text):
            return True
    return False

def _extract_fee_code(text):
    """Extracts the fee code number from a heading text."""
    match = re.search(r'Takst\s+(\w+)', text)
    return match.group(1) if match else None

def _find_main_section_for_tag(tag):
    """Finds the main H2 section heading for a given tag."""
    previous = tag.find_all_previous('h2')
    if previous:
        return previous[0].get_text(strip=True)
    return None

def _strip_code_fences(text):
    """Removes the markdown code fences from the LLM's response."""
    return re.sub(r'^```yaml\s*|```$', '', text.strip(), flags=re.MULTILINE).strip()

async def scrape_helfo_fee_codes(url: str):
    """
    Scrapes the Helfo website for fee codes and their descriptions.
    This version is updated to handle varying HTML structures for sub-sections.

    Args:
        url (str): The URL of the Helfo page.

    Returns:
        dict: A dictionary of scraped fee codes and their content.
    """
    print("Fetching Helfo page...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page: {e}")
        return {}

    soup = BeautifulSoup(resp.content, 'html.parser')
    fee_codes = {}
    fee_code_headings = soup.find_all(lambda tag: _is_fee_code_heading(tag))

    for h in fee_code_headings:
        fee_code = _extract_fee_code(h.get_text())
        if not fee_code:
            continue

        main_section = _find_main_section_for_tag(h) or ""
        content = {"Forskriftstekst": "", "Forklaring": "", "Eksempel": ""}
        current_subsection = None

        # Iterate through siblings to find subsections and their content
        for sibling in h.next_siblings:
            if isinstance(sibling, str):
                continue

            # If we hit a new fee code heading, stop.
            if _is_fee_code_heading(sibling):
                break

            if sibling.name == 'p':
                strong_tag = sibling.find('strong')
                if strong_tag:
                    sub_text = strong_tag.get_text(strip=True).lower()
                    if 'forskriftstekst' in sub_text:
                        current_subsection = "Forskriftstekst"
                        # The content is in the same p tag or a sibling
                        content_text = sibling.get_text(separator="\n", strip=True)
                        content[current_subsection] += content_text.replace(strong_tag.get_text(strip=True) + ":", "", 1).strip()
                    elif 'forklaring' in sub_text:
                        current_subsection = "Forklaring"
                        content_text = sibling.get_text(separator="\n", strip=True)
                        content[current_subsection] += content_text.replace(strong_tag.get_text(strip=True) + ":", "", 1).strip()
                    elif 'eksempel' in sub_text:
                        current_subsection = "Eksempel"
                        content_text = sibling.get_text(separator="\n", strip=True)
                        content[current_subsection] += content_text.replace(strong_tag.get_text(strip=True) + ":", "", 1).strip()
                elif current_subsection:
                    # Append all other text to the current subsection
                    content_text = sibling.get_text(separator="\n", strip=True)
                    content[current_subsection] += "\n" + content_text

            # Handle list items
            if sibling.name in ['ul', 'ol'] and current_subsection:
                list_text = sibling.get_text(separator="\n", strip=True)
                content[current_subsection] += "\n" + list_text


        fee_codes[fee_code] = {
            "main_section": main_section,
            "Forskriftstekst": content["Forskriftstekst"].strip(),
            "Forklaring": content["Forklaring"].strip(),
            "Eksempel": content["Eksempel"].strip(),
        }

    print(f"Extracted {len(fee_codes)} Helfo fee codes.")
    return fee_codes

async def process_with_gemini(fee_code: str, content_dict: dict) -> dict:
    """
    Processes scraped content with Gemini to generate structured data.
    This version is more robust and returns a default structure if no content is found.

    Args:
        fee_code (str): The Helfo fee code.
        content_dict (dict): The dictionary of scraped content.

    Returns:
        dict: A dictionary of structured data.
    """
    if not any(content_dict.values()):
        print(f"No content found for {fee_code}. Returning default structure.")
        return {
            "name": f"Ukjent HELFO oppgave ({fee_code})",
            "required_terms": [],
            "warn_terms": [],
            "suggestions": "",
            "version": "HELFO-2025-01",
            "requirement": "Ingen kravspesifikasjon funnet.",
            "severity": {
                "fail": f"Krav mangler for HELFO oppgave {fee_code}.",
                "warn": f"Anbefalt informasjon mangler for HELFO oppgave {fee_code}."
            }
        }

    try:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
    except ValueError as e:
        print(f"Error configuring Gemini: {e}")
        return {}

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
    {content_dict.get('Forskriftstekst', '')}

    Forklaring:
    {content_dict.get('Forklaring', '')}

    Eksempel:
    {content_dict.get('Eksempel', '')}

    Please respond with only YAML (no explanations).
    """

    print(f"Generating structured YAML for {fee_code} with Gemini...")
    try:
        response = await model.generate_content_async(prompt)
        yaml_text = response.candidates[0].content.parts[0].text.strip()
        yaml_text = _strip_code_fences(yaml_text)
        data = yaml.safe_load(yaml_text)

        suggestions_field = data.get('suggestions')
        if isinstance(suggestions_field, list):
            data['suggestions'] = ' '.join(suggestions_field) if suggestions_field else ''

        return data
    except Exception as e:
        print(f"Failed to process {fee_code} with Gemini: {e}")
        return {}
