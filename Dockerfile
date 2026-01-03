FROM python:3.12-slim

ENV PYTHONPATH="/app:${PYTHONPATH}"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Copy requirements
COPY requirements.txt .

# Install PyTorch CPU version FIRST (with explicit index URL)
#RUN pip install --no-cache-dir torch==2.5.1 \
#    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy FAQ data
COPY . .
COPY data/faq.json data/faq.json

EXPOSE 8501

# Set environment variables for Streamlit
#ENV STREAMLIT_SERVER_HEADLESS=true
#ENV STREAMLIT_SERVER_ENABLECORS=false
#ENV STREAMLIT_SERVER_PORT=8501

# Run Streamlit app
#CMD ["streamlit", "run", "app/app.py"]
ENTRYPOINT ["streamlit", "run", "/app/app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]