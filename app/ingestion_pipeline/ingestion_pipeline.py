import yaml
import yaml
from datetime import datetime
from typing import Dict, List, Type, Any
from pydantic import ValidationError
import os
import asyncio
import argparse

# Import data models and scraper functions from the same directory
from .data_models import ServiceCode, ICD10Code, TakstKode
from .helfo_scraper import scrape_helfo_fee_codes, process_with_gemini
# from .finnkode_scraper import scrape_finnkode_data # Assuming we'll add this later
from .xml_scraper import scrape_helsedirektoratet_xml

# --- Configuration ---
# Define the data sources and their URLs.
# This dictionary is the central configuration for our MLOps pipeline.
DATA_SOURCES = {
    "helfo": {
        "url": 'https://www.helfo.no/lege/Regelverk-og-takster-for-lege/ofte-brukte-takstar-for-legar',
        "scraper": scrape_helfo_fee_codes,
        "llm_processor": process_with_gemini,
        "output_file": "../../data/helfo_fee_codes_structured.yaml",
        "model": ServiceCode
    },
    # NEW: Data source for the structured XML Taksttabell
    "helsedir_takster": {
        # Using a placeholder URL for the XML file as discussed.
        "url": 'https://www.helsedirektoratet.no/tilskudd-og-finansiering/finansiering/andre-finansieringsordninger/takster/Takster_Fysioterapeut_24022025.xml',
        "scraper": scrape_helsedirektoratet_xml,
        "llm_processor": None,  # No LLM needed for structured data
        "output_file": "../../data/helsedir_takster.yaml",
        "model": TakstKode
    },
    # NOTE: The finnkode source for ICD-10 is a placeholder for a future task.
    "finnkode": {
        "url": 'https://finnkode.helsedirektoratet.no/icd10',
        # "scraper": scrape_finnkode_data,
        "scraper": None, # Placeholder
        "llm_processor": None,
        "output_file": "../../data/finnkode_icd10_structured.yaml",
        "model": ICD10Code
    }
}

async def run_pipeline(source_name: str) -> Dict[str, Any]:
    """
    Executes the full ETL pipeline for a given data source.

    Args:
        source_name (str): The name of the data source to process (e.g., 'helfo').

    Returns:
        Dict[str, Any]: A dictionary of validated Pydantic models or raw data.
    """
    if source_name not in DATA_SOURCES:
        raise ValueError(f"Unknown data source: {source_name}")

    source_config = DATA_SOURCES[source_name]
    url = source_config['url']
    scraper_func = source_config['scraper']
    llm_processor_func = source_config['llm_processor']
    output_file = source_config['output_file']
    data_model: Type[BaseModel] = source_config['model']

    print(f"Starting ingestion pipeline for '{source_name}'...")
    if not scraper_func:
        print(f"No scraper function defined for {source_name}. Skipping.")
        return {}

    raw_data = await scraper_func(url)
    if not raw_data:
        print(f"No data scraped from {source_name}. Aborting pipeline.")
        return {}

    structured_data: Dict[str, Any] = {}
    if llm_processor_func:
        for code, content in raw_data.items():
            llm_output = await llm_processor_func(code, content)
            if llm_output:
                try:
                    validated_data = data_model(**llm_output)
                    structured_data[code] = validated_data
                    print(f"Successfully validated code {code}.")
                except ValidationError as e:
                    print(f"Validation failed for code {code}: {e}")
                    continue
    else:
        # If no LLM processing is needed, validate the raw scraped data
        for code, content in raw_data.items():
            try:
                validated_data = data_model(**content)
                structured_data[code] = validated_data
                print(f"Successfully validated code {code}.")
            except ValidationError as e:
                print(f"Validation failed for code {code}: {e}")
                continue

    # Save the structured data to a YAML file
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump({k: v.model_dump() for k, v in structured_data.items()}, f, allow_unicode=True, sort_keys=False)
        print(f"Structured data saved to {output_file}")
    except IOError as e:
        print(f"Error saving file: {e}")

    return structured_data


async def main(source: str):
    """
    Main function to run the complete MLOps ingestion pipeline.

    Args:
        source (str): The name of the data source to process ('helfo', 'xml', or 'all').
    """
    if source in ["helfo", "all"]:
        await run_pipeline("helfo")

    if source in ["xml", "all"]:
        await run_pipeline("helsedir_takster")

    print("\nMLOps Data Ingestion Pipeline has finished all tasks.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the MLOps data ingestion pipeline for specified sources.")
    parser.add_argument("--source", type=str, choices=["helfo", "xml", "all"], default="all",
                        help="Specify which data source to run the pipeline for. Defaults to 'all'.")
    args = parser.parse_args()
    asyncio.run(main(args.source))
