FROM python:3.11-bullseye

# Set working directory
WORKDIR /app

# Cập nhật apt và cài các thư viện hệ thống cần thiết
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libzbar0 \         # cho pyzbar
        libgl1-mesa-glx \  # cho OpenCV hiển thị ảnh (optional nếu headless)
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
        ca-certificates \
        wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy toàn bộ source code vào container
COPY . .

# Mở port Streamlit
EXPOSE 8501

# CMD chạy Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false"]
