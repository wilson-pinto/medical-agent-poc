import requests
from bs4 import BeautifulSoup
import re

async def scrape_finnkode_data(url: str):
    """
    Scrapes the FinnKode website for ICD-10 diagnosis codes.

    Args:
        url (str): The URL of the FinnKode page.

    Returns:
        dict: A dictionary of scraped ICD-10 codes, names, and descriptions.
    """
    print(f"Scraping FinnKode from {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page: {e}")
        return {}

    soup = BeautifulSoup(resp.content, 'html.parser')
    icd10_codes = {}

    for code_tag in soup.find_all(['h3', 'h4']):
        code_text = code_tag.get_text(strip=True)
        match = re.search(r'([A-Z]\d{2}(?:\.\d)?)\s*-\s*(.+)', code_text)
        if match:
            code = match.group(1).strip()
            name = match.group(2).strip()
            description = ""
            next_tag = code_tag.find_next_sibling()
            if next_tag and next_tag.name == 'p':
                description = next_tag.get_text(strip=True)

            icd10_codes[code] = {
                "code": code,
                "name": name,
                "description": description
            }
            print(f"Found ICD-10 code: {code}")

    print(f"Extracted {len(icd10_codes)} ICD-10 codes.")
    return icd10_codes