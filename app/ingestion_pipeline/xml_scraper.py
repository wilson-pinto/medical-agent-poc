import requests
import xml.etree.ElementTree as ET
import re
from typing import Dict, Any

async def scrape_helsedirektoratet_xml(url: str) -> Dict[str, Any]:
    """
    Scrapes a Taksttabell XML file from helsedirektoratet.no and parses it.

    Args:
        url (str): The URL of the XML file.

    Returns:
        Dict[str, Any]: A dictionary where keys are the takstkoder and values are
                        dictionaries of the extracted data.
    """
    print(f"Fetching and parsing XML from: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching XML: {e}")
        return {}

    root = ET.fromstring(response.content)
    takster = {}

    # The XML structure might have a namespace, so we need to handle that.
    # We find the namespace from the root element.
    namespace_match = re.match(r'\{.*\}', root.tag)
    namespace = namespace_match.group(0) if namespace_match else ''

    # The tag name for a single takst code is 'takst'
    for takst_element in root.findall(f'{namespace}takst'):
        try:
            takst_data = {}
            # Extract each field by its tag name within the takst element
            for child in takst_element:
                tag_name = child.tag.replace(namespace, '')
                text = child.text.strip() if child.text else None

                # Handle lists of codes (e.g., ugyldigKombinasjon)
                if tag_name in ['ugyldigKombinasjon', 'kreverTakst', 'kreverProsedyre', 'kreverDiagnose']:
                    if text:
                        # The text is a space-separated list of codes
                        takst_data[tag_name] = text.split()
                    else:
                        takst_data[tag_name] = []
                # Convert relevant fields to float or int
                elif tag_name in ['honorar', 'refusjon', 'egenandel']:
                    takst_data[tag_name] = float(text) if text else 0.0
                elif tag_name in ['minimumTidsbruk']:
                    takst_data[tag_name] = int(text) if text else None
                else:
                    takst_data[tag_name] = text

            # Use the takstkode as the key for our dictionary
            takstkode = takst_data.get('takstkode')
            if takstkode:
                takster[takstkode] = takst_data

        except Exception as e:
            print(f"Error parsing takst element: {e}")
            continue

    print(f"Successfully parsed {len(takster)} takst codes from XML.")
    return takster