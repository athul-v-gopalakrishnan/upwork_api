# --- Base image with Python and Playwright ---
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble


WORKDIR /app

# RUN apt-get install -y curl

RUN apt-get update && \
    apt-get install -y curl wget xvfb gcc libpq-dev \
    gnupg2 \
    unzip \
    libx11-xcb1 \
    libfontconfig1 \
    libxi6 \
    libxrender1 \
    libglib2.0-0 \
    libnss3 \
    libgdk-pixbuf2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxslt1.1 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libdbus-1-3 \
    fonts-liberation \
    libappindicator3-1 \
    libnspr4 \
    libxrandr2 \
    libgbm1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list


# Install Google Chrome
RUN apt-get update && apt-get install -y google-chrome-stable

# Copy only requirements first for better caching
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# Copy the entire app (all code and subfolders)
COPY . /app

# Expose the FastAPI port
EXPOSE 8000

# ✅ Ensure start.sh is executable + correct line endings
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]

# --- End of Dockerfile ---