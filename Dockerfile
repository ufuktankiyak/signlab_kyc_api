FROM python:3.12-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download PaddleOCR models at build time (no internet access required at runtime)
RUN python -c "import paddleocr._common_args as c; _o=c.parse_common_args; c.parse_common_args=lambda k: _o({x:k[x] for x in k if x!='show_log'}); from paddleocr import PaddleOCR; PaddleOCR(lang='en')"

# Proje files
COPY . .

# OCR service port
EXPOSE 5001

# Run with uvicorn — OCR internal service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5001"]
