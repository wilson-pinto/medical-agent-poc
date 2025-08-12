# Data Ingestion Pipeline

This document provides instructions for running the MLOps data ingestion pipeline, which scrapes data from various sources and structures it into YAML files. The script is located at `app/ingestion_pipeline/ingestion_pipeline.py`.

---

## 🚀 Usage

Navigate to the `app/ingestion_pipeline` directory in your terminal and execute the script with the `python` command. You can specify which data source to scrape using the `--source` argument.

**General Command:**

```bash
python ingestion_pipeline.py --source <option>
```

---

## Options for `--source`

| Option | Description |
|--------|-------------|
| `helfo` | Scrapes only the Helfo website. Generates `helfo_fee_codes_structured.yaml` in the `data/` directory. |
| `xml`   | Scrapes only the Helsedirektoratet XML file. Generates `helsedir_takster.yaml` in the `data/` directory. |
| `all`   | Scrapes all available data sources. This is the default if no `--source` argument is provided. |

---

## 📝 Examples

**To run the pipeline for the XML file only:**

```bash
python ingestion_pipeline.py --source xml
```

**To run both pipelines at once:**

```bash
python ingestion_pipeline.py --source all
```

The processed data will be saved as separate YAML files in the root `data/` directory.
