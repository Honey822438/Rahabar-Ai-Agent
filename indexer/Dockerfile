FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp

# tesseract and poppler are the OCR path for scanned PDFs.
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin indexer
COPY pipeline ./pipeline

USER 10001
CMD ["python", "-m", "pipeline.run"]
