FROM python:3.11-slim

# Cài thư viện hệ thống cần thiết
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libzbar0 \
        libgl1-mesa-glx \
        libglib2.0-0 \
        && rm -rf /var/lib/apt/lists/*

# Tạo thư mục app
WORKDIR /app

# Copy requirements
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy toàn bộ source code
COPY . .


# Mở port Streamlit
EXPOSE 8501

# Command chạy Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false"]
