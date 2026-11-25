# RAHBAR on minikube: fresh cluster → working RAGOps pipeline (Assignment 03, Part F)

Everything runs in namespace `rahbar`. Run one heavy job at a time (OCR, embedding and eval share
the laptop's CPU and the host Ollama; running them in parallel caused Ollama timeouts, see PLAN-A3).

## 0. Prerequisites (once)
```bash
OLLAMA_HOST=0.0.0.0 ollama serve &          # host Ollama, nomic-embed-text pulled
make cluster                                 # minikube (calico) + metrics-server + ingress
make images TAG=dev                          # api, indexer, ui, eval: built inside minikube
# Secret: created by hand, never from a file in Git (keys loaded into your shell first)
kubectl create namespace rahbar --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic rahbar-secret -n rahbar \
  --from-literal=LLM_API_KEY="$LLM_API_KEY" --from-literal=GROQ_API_KEY="$GROQ_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## F1. Stack + data lake PVC
```bash
kubectl delete job indexer -n rahbar --ignore-not-found   # Jobs are immutable
kubectl apply -k k8s/overlays/dev
kubectl get pvc -n rahbar                                  # data (lake/traces/results), corpus, chroma, redis
```
The `data` PVC holds `/data/lake/{incoming,verified,quarantine,archive,cache}`, the manifest, the
traces and the results. `cache/` keeps extraction/OCR output by file sha256, so a re-run never OCRs
a scanned PDF twice.

## F2. Ingest (the only writer) + eval Job + gate ConfigMap
```bash
kubectl wait -n rahbar --for=condition=complete job/indexer --timeout=40m
kubectl logs -n rahbar job/indexer | tail -30            # verification table + sync counts
kubectl create job --from=cronjob/reindex reindex-manual-1 -n rahbar   # same work on demand: 0 embedded

kubectl apply -f k8s/a3/gate-configmap.yaml
kubectl delete job eval -n rahbar --ignore-not-found && kubectl apply -f k8s/eval-job.yaml
kubectl wait -n rahbar --for=condition=complete job/eval --timeout=60m   # Failed = gate FAIL
kubectl logs -n rahbar job/eval | tail -25
```
Change a threshold with no rebuild: `kubectl edit configmap gate-config -n rahbar` (or edit
`k8s/a3/gate-configmap.yaml` and re-apply), then re-run the eval Job. The verdict changes.

## F3. Candidate → gate → rolling update → rollback
```bash
kubectl apply -f k8s/a3/candidate-build-job.yaml           # builds collection rahbar_c600 (600/100)
kubectl wait -n rahbar --for=condition=complete job/build-candidate --timeout=30m
kubectl apply -f k8s/a3/candidate.yaml                     # api-candidate Deployment + Service
# eval the candidate: EVAL_COLLECTION=rahbar_c600, EVAL_LABEL=k8s-c600 in k8s/eval-job.yaml
# gate PASS -> promote: roll the live api onto the candidate collection (maxUnavailable: 0)
kubectl set env deployment/api -n rahbar CHROMA_COLLECTION=rahbar_c600
kubectl rollout status deployment/api -n rahbar
# a bad release -> back to the previous ReplicaSet (previous collection)
kubectl rollout undo deployment/api -n rahbar && kubectl rollout status deployment/api -n rahbar
```
A candidate stopped by the gate: `EVAL_COLLECTION=rahbar_c600`, `TOP_K=1` → the Job ends `Failed`
and the live api is never touched.

## F4. Traces and metrics
```bash
kubectl logs -n rahbar deploy/api | grep '"trace"' | tail -1      # one JSON trace per query
kubectl exec -n rahbar deploy/api -- tail -1 /data/traces/traces.jsonl
kubectl port-forward -n rahbar svc/api 8000:8000 &  curl -s localhost:8000/metrics | head
```

## F5. Requests and limits
```bash
kubectl top pods -n rahbar          # under load; numbers and the chosen requests/limits in the report
```
