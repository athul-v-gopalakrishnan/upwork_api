# --- Base image with Python and Playwright ---
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble


WORKDIR /app

# Copy only requirements first for better caching
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && \
    apt-get install -y xvfb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99

# Copy the entire app (all code and subfolders)
COPY . /app

# Expose the FastAPI port
EXPOSE 8000

# Start the FastAPI app (adjust if your entry is different)
CMD xvfb-run --server-args="-screen 0 1920x1080x24" uvicorn main:app --host 0.0.0.0 --port 8000
# --- End of Dockerfile ---