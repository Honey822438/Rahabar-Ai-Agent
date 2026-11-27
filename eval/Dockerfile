# A3 eval Job image (F2). Built from the repo root: docker build -f eval/Dockerfile -t rahbar-eval:<sha> .
# Runs the suite in-process against Chroma + host Ollama + the hosted LLM, then the release gate.
FROM python:3.12-slim-bookworm

# Debian security fixes the base tag lags behind (e.g. CVE-2025-6020 libpam, fixed in 1.5.2-6+deb12u3).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp

WORKDIR /srv
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt pyyaml==6.0.2 && \
    useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin eval
COPY api/app ./api/app
COPY eval/run_suite.py eval/gate.py eval/golden.jsonl eval/drift_probes.jsonl ./eval/
COPY eval/suite ./eval/suite
COPY eval/pairs ./eval/pairs
# noise documents for the component-level noise test (it builds a scratch <collection>_noise)
COPY eval/noise ./eval/noise
# The gate's baseline result. Thresholds come from the gate ConfigMap, not this copy.
COPY eval/results/20261126T160622Z-k8s-baseline.json ./eval/results/
COPY config/gate.yaml ./config/gate.yaml

USER 10001
CMD ["python", "eval/run_suite.py", "--help"]
