# Ingestion Service for Medical Codes

This service is a robust MLOps pipeline designed to **scrape**, **process**, and **structure** medical code data from official Norwegian health authority websites — specifically **Helfo** and **FinnKode**.

Built using **FastAPI** for the web interface and **Gemini API** (Google AI Studio) for natural language processing, the pipeline ensures structured, validated outputs in standardized YAML format.

---

## 🚀 Features

- **Data Scraping**: Fetches the latest medical fee codes from Helfo and ICD-10 diagnosis codes from FinnKode.
- **Intelligent Processing**: Uses the Gemini API to convert raw text into structured YAML format.
- **Data Validation**: Uses Pydantic models to enforce schema correctness.
- **API Endpoints**: FastAPI server with endpoints to check service status and run pipelines.
- **Data Persistence**: Structured YAML files are saved in the `data/` directory.

---

## 🔧 Prerequisites

- Python 3.8 or higher
- A **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/)

---

## 📦 Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

Set up your environment:

1. Create a `.env` file in the root directory.
2. Add your Gemini API key:

```env
GEMINI_API_KEY="your_api_key_here"
```

---

## 🚦 Usage

### Start the FastAPI server

```bash
uvicorn main:app --reload
```

The server will be available at: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Check Status

```bash
curl http://127.0.0.1:8000/status
```

### Run Ingestion Pipeline

Replace `{source_name}` with either `helfo` or `finnkode`:

**Run for Helfo**

```bash
curl -X POST http://127.0.0.1:8000/run_pipeline/helfo
```

**Run for FinnKode**

```bash
curl -X POST http://127.0.0.1:8000/run_pipeline/finnkode
```

Processed data will be saved to the `data/` directory.

---

## 📁 File Structure

```
.
├── main.py                # FastAPI application entry point
├── ingestion_pipeline.py  # Orchestrates data scraping and processing
├── helfo_scraper.py       # Scraper for Helfo medical fee codes
├── finnkode_scraper.py    # Scraper for FinnKode ICD-10 codes
├── data_models.py         # Pydantic models for validation
├── requirements.txt       # Python dependencies
├── data/                  # Output directory for YAML files
└── .env                   # Environment variables (not committed)
```

---

## 🤝 Contributing

We welcome contributions! Feel free to open an issue or submit a pull request if you have ideas or improvements.

---

## 📜 License

MIT License — feel free to use and modify this project.

---

## 📬 Contact

For questions or collaboration, reach out via Issues or Pull Requests.
