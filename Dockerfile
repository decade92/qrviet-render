FROM python:3.10-slim

# Cài các gói hệ thống cần thiết để chạy opencv-python và streamlit
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục ứng dụng
WORKDIR /app

# Copy files
COPY . /app

# Cài thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Mặc định chạy streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.enableCORS=false"]