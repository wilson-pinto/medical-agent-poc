# ---- Base image ----
FROM python:3.10-slim

# ---- Set working directory ----
WORKDIR /app

# ---- Copy only requirements first (layer cache optimization) ----
COPY requirements.txt .

# ---- Install dependencies ----
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Copy the rest of your app ----
COPY . .

# ---- Default command ----
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
