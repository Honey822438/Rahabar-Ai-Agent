#!/usr/bin/env bash
# Pre-demo health check: prints PASS/FAIL per item, exits 1 if anything fails.
#   scripts/demo_check.sh
# Light: one /api/ask call (one LLM request). Never prints secret values.
set -uo pipefail
cd "$(dirname "$0")/.."
NS=rahbar
PY=${PY:-.venv/bin/python}
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
FAILS=0
check() {  # check "name" cmd...
  local name=$1; shift
  if out=$("$@" 2>&1); then printf 'PASS  %-44s %s\n' "$name" "${out%%$'\n'*}"
  else printf 'FAIL  %-44s %s\n' "$name" "$(tail -1 <<<"$out")"; FAILS=$((FAILS+1)); fi
}

c_minikube() { minikube status --format '{{.Host}}/{{.Kubelet}}/{{.APIServer}}' | grep -qx 'Running/Running/Running' && kubectl get ns $NS >/dev/null && echo "Running"; }
c_pods() {
  local bad
  bad=$(kubectl get pods -n $NS --no-headers | awk '$3!="Completed" { split($2,a,"/"); if (a[1]!=a[2] || $3!="Running") print $1" "$2" "$3 }')
  [ -z "$bad" ] && echo "$(kubectl get pods -n $NS --no-headers | grep -c Running) running, all Ready" || { echo "not ready: $bad"; return 1; }
}
c_hpa() { kubectl get hpa api -n $NS --no-headers | grep -v unknown | awk '{print $3,$4}' | grep . || { echo "HPA <unknown>: minikube ssh -- 'sudo crictl stop $(sudo crictl ps -q --name kube-controller-manager)'"; return 1; }; }
c_ollama_bind() {
  ss -ltn | awk '$4 ~ /:11434$/ {print $4}' | grep -qE '^(0\.0\.0\.0|\*|\[::\]):11434$' \
    && echo "listening on all interfaces" || { echo "Ollama bound to $(ss -ltn | awk '$4 ~ /:11434$/ {print $4}' | head -1) (want 0.0.0.0)"; return 1; }
}
c_ollama_cluster() { minikube ssh -- "curl -s -m5 http://host.minikube.internal:11434/api/tags" | grep -q nomic-embed-text && echo "nomic-embed-text reachable from minikube"; }
c_secret() {
  local keys; keys=$(kubectl get secret rahbar-secret -n $NS -o jsonpath='{.data}' | "$PY" -c 'import json,sys;print(" ".join(k for k,v in json.load(sys.stdin).items() if v))')
  for k in LLM_API_KEY GROQ_API_KEY; do grep -qw "$k" <<<"$keys" || { echo "missing $k"; return 1; }; done; echo "LLM_API_KEY + GROQ_API_KEY set"
}
c_gate_cm() { kubectl get configmap gate-config -n $NS -o jsonpath='{.data.gate\.yaml}' | grep -E '^baseline:.*k8s-baseline' ; }
c_collections() {
  kubectl exec -n $NS deploy/api -- python -c "
import chromadb;c=chromadb.HttpClient(host='chroma',port=8000)
n={x.name:x.count() for x in c.list_collections()}
miss=[k for k in ('rahbar','rahbar_c600') if n.get(k,0)==0]
print('missing/empty: '+','.join(miss) if miss else 'rahbar=%d rahbar_c600=%d'%(n['rahbar'],n['rahbar_c600']));raise SystemExit(1 if miss else 0)"
}
c_eval_image() {
  minikube ssh -- "sudo ctr -n k8s.io run --rm docker.io/library/rahbar-eval:dev democheck\$RANDOM sh -c 'ls /srv/eval/results/*k8s-baseline.json && grep -q k8s-baseline /srv/config/gate.yaml'" | grep -o '[^/]*k8s-baseline.json'
}
c_ask() {
  kubectl exec -n $NS deploy/api -- python -c "
import json,urllib.request as u
r=json.loads(u.urlopen(u.Request('http://localhost:8000/api/ask',json.dumps({'question':'What CGPA puts an undergraduate student on academic warning?'}).encode(),{'Content-Type':'application/json','X-Request-ID':'democheck$$'}),timeout=90).read())
ok=r.get('answered_from_context') and r.get('citations')
print(('cited answer, %d citation(s), id %s'%(len(r['citations']),r['request_id'])) if ok else 'no cited answer: '+json.dumps(r)[:150]);raise SystemExit(0 if ok else 1)" > "$TMP/ask.txt"
  local rc=$?; cat "$TMP/ask.txt"; return $rc
}
c_trace_written() {
  sleep 2
  kubectl exec -n $NS deploy/api -- grep -h "democheck$$" /data/traces/traces.jsonl > "$TMP/traces.jsonl" \
    && [ -s "$TMP/traces.jsonl" ] && echo "trace democheck$$ in /data/traces/traces.jsonl"
}
c_trace_tool() {
  local id; id=$("$PY" -c "import json;print(json.loads(open('$TMP/traces.jsonl').readline())['trace_id'])") || return 1
  "$PY" -m tools.trace "$id" --file "$TMP/traces.jsonl" >/dev/null && echo "prompt rebuilt, hash matches ($id)"
}

echo "== RAHBAR demo check $(date -u +%FT%TZ) =="
check "minikube up + namespace rahbar"            c_minikube
check "all rahbar pods Ready"                     c_pods
check "HPA api reads CPU (not <unknown>)"       c_hpa
check "Ollama listening on 0.0.0.0:11434"         c_ollama_bind
check "Ollama reachable from the cluster"         c_ollama_cluster
check "Secret rahbar-secret keys"                 c_secret
check "gate ConfigMap present (k8s-baseline)"     c_gate_cm
check "Chroma collections rahbar + rahbar_c600"   c_collections
check "eval image ships k8s-baseline"             c_eval_image
check "test question -> cited answer"             c_ask
check "trace written to the volume"               c_trace_written
check "trace tool rebuilds the prompt"            c_trace_tool
echo "== $([ $FAILS -eq 0 ] && echo 'ALL PASS' || echo "$FAILS FAIL") =="
exit $((FAILS > 0))
