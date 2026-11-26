#!/usr/bin/env bash
# F4: /metrics through a port-forward (light).
set -euo pipefail
kubectl port-forward -n rahbar svc/api 8000:8000 >/dev/null 2>&1 & PF=$!
trap 'kill $PF' EXIT; sleep 3
curl -s localhost:8000/metrics | grep -E "^rahbar_|^# HELP rahbar_" | head -40
