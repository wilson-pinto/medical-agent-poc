import sys
import os
import uvicorn
from fastapi import FastAPI
import asyncio
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingestion_pipeline import run_pipeline, DATA_SOURCES
from data_models import Status
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Helsedirektoratet and Helfo Data Ingestion Pipeline",
    description="A microservice to scrape and structure medical codes.",
)

pipeline_status = Status()

@app.get("/status", response_model=Status)
def get_status():
    """
    Get the current status of the data ingestion pipeline.
    """
    return pipeline_status

@app.post("/run_pipeline/{source_name}", response_model=Status)
async def run_pipeline_endpoint(source_name: str):
    """
    Trigger the data ingestion pipeline for a specific data source.

    Args:
        source_name (str): The name of the data source (e.g., 'helfo').
    """
    if source_name not in DATA_SOURCES:
        pipeline_status.status = "error"
        pipeline_status.message = f"Unknown data source: {source_name}"
        return pipeline_status

    print(f"API call received: running pipeline for {source_name}")
    pipeline_status.status = "running"
    pipeline_status.message = f"Pipeline for {source_name} started."
    pipeline_status.last_run = datetime.now().isoformat()

    try:
        # Run the pipeline in the background to not block the API response
        asyncio.create_task(run_pipeline(source_name))
        pipeline_status.status = "success"
        pipeline_status.message = f"Pipeline for {source_name} triggered successfully."
    except Exception as e:
        pipeline_status.status = "error"
        pipeline_status.message = f"An error occurred while starting the pipeline: {e}"
        print(f"Error in API endpoint: {e}")

    return pipeline_status

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("Set the GEMINI_API_KEY environment variable")

    # Run the FastAPI application using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
