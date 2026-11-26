#!/usr/bin/env bash
# F3 demo: promote the gated candidate collection with a rolling update (maxUnavailable: 0),
# send one query (trace shows rahbar_c600), roll back with `rollout undo`, send the same query
# again (trace shows the previous collection). Light: no indexing, ~4 LLM calls.
set -euo pipefail
NS=rahbar; Q='What CGPA does an undergraduate need to stay off academic warning?'
ask() {
  kubectl exec -n $NS deploy/api -- python -c "import json,urllib.request as u;r=u.Request('http://localhost:8000/ask',json.dumps({'question':'''$Q'''}).encode(),{'Content-Type':'application/json'});print(u.urlopen(r).read().decode()[:300])"
  sleep 2
  kubectl exec -n $NS deploy/api -- tail -1 /data/traces/traces.jsonl \
    | python3 -c "import json,sys;t=json.load(sys.stdin);print('TRACE',t['trace_id'],'collection=',t['collection'],'embedding=',t['embedding'])"
}
kubectl rollout history deployment/api -n $NS
echo "=== before ==="; ask
echo "=== promote candidate ==="
kubectl set env deployment/api -n $NS CHROMA_COLLECTION=rahbar_c600
kubectl rollout status deployment/api -n $NS --timeout=10m
ask
echo "=== rollback ==="
kubectl rollout undo deployment/api -n $NS
kubectl rollout status deployment/api -n $NS --timeout=10m
kubectl rollout history deployment/api -n $NS
ask
