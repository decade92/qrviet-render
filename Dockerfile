FROM python:3.10-slim

# Cài thư viện hệ thống cần thiết cho pyzbar, OpenCV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libzbar0 \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Copy và cài dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy toàn bộ source code
COPY . .

# Mở port Streamlit
EXPOSE 8501

# Chạy Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false"]
