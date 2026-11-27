FROM python:3.12-slim-bookworm

# Debian security fixes the base tag lags behind (e.g. CVE-2025-6020 libpam, fixed in 1.5.2-6+deb12u3).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY app ./app

USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
