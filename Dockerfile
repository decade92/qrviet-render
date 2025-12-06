FROM python:3.11-bullseye

WORKDIR /app

# 1. Cập nhật, cài thư viện hệ thống + Java
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    libzbar0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    wget \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Tạo thư mục app
WORKDIR /app

# 3. Copy requirements
COPY requirements.txt .

# 4. Cài Python packages
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy toàn bộ source code
COPY . .

# 6. Download ZXing offline jar (nếu chưa có trong assets)
RUN mkdir -p assets/zxing && \
    wget -O assets/zxing/javase-3.5.0.jar https://repo1.maven.org/maven2/com/google/zxing/javase/3.5.0/javase-3.5.0.jar

# 7. Mở cổng Streamlit
EXPOSE 8501

# 8. Lệnh khởi chạy Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
