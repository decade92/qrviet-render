FROM python:3.11-bullseye

WORKDIR /app

# Cài thư viện hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    ca-certificates \
    wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài Python packages
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy toàn bộ source code
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false"]
