# ---- Base image ----
FROM python:3.10-slim

# ---- Set working directory ----
WORKDIR /app

# ---- Copy only requirements first (layer cache optimization) ----
COPY requirements.txt .

# ---- Install dependencies ----
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Set model cache envs ----
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/root/.cache/sentence_transformers

# ---- Preload sentence-transformer models into image ----
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('NbAiLab/nb-sbert-base')"

COPY . .

# ---- Expose port ----
EXPOSE 8000

# ---- Default command ----
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

/*
# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory
WORKDIR /app

# Install any needed packages specified in requirements.txt
# (In this case, we'll install Flask and redis-py directly)
RUN pip install Flask redis

# Copy the current directory contents into the container at /app
COPY . /app

# Run the app.py when the container launches
CMD ["python", "app.py"]

*/