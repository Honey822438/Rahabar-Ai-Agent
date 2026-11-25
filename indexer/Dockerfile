# Built from the repo root: docker build -f indexer/Dockerfile .
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp

# tesseract and poppler are the OCR path for scanned PDFs.
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY indexer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin indexer
COPY indexer/pipeline ./pipeline
# The init container downloads the corpus with these; PDFs are never in the image.
COPY corpus/fetch.py corpus/sources.yaml ./corpus/
# Mount point for the corpus PVC: sources.yaml must sit next to raw/ (doc_ids for the lake).
RUN mkdir -p /srv/corpus/raw && chown 10001 /srv/corpus/raw
# A3 Batch B: small text/Markdown documents (no PDFs), seeded into the lake by the ingest Job.
COPY data/batch_b ./batch_b

USER 10001
CMD ["python", "-m", "pipeline.run"]
