# Demo runbook (A3)

Run from the repo root with the venv active (`source .venv/bin/activate`). Run only one heavy job at a time.

## 0. Before the demo (≈ 2 min)
```bash
OLLAMA_HOST=0.0.0.0 ollama serve &          # skip this if the systemd service already listens on 0.0.0.0
minikube start                              # skip this if it is already running
scripts/demo_check.sh                       # every line must say PASS, exit 0
```

## 1. Eval Job (≈ 12 min; start it first and talk while it runs)
```bash
kubectl delete job eval -n rahbar --ignore-not-found && kubectl apply -f k8s/eval-job.yaml
kubectl logs -n rahbar -f job/eval                 # module -> component -> e2e, then the gate table
kubectl get job eval -n rahbar                     # Complete = gate PASS, Failed = gate FAIL
```
Gate change with no rebuild: run `scripts/demo/f2_configmap_gate.sh` (two evals, ≈ 25 min). Run it only if there is time.
To show a candidate: `kubectl delete job eval -n rahbar && kubectl apply -f k8s/eval-job-candidate.yaml`.

## 2. Open a trace
```bash
kubectl exec -n rahbar deploy/api -- tail -1 /data/traces/traces.jsonl | python -m json.tool | head -60
python -m tools.trace 2f213c99a8ea41e597f4a678946f98e3 --file data/traces/traces.jsonl   # wrong abstention (D5)
```
For a live trace, take the newest record from the volume and rebuild its prompt:
```bash
kubectl exec -n rahbar deploy/api -- tail -1 /data/traces/traces.jsonl > /tmp/t.jsonl
python -m tools.trace "$(python -c 'import json;print(json.load(open("/tmp/t.jsonl"))["trace_id"])')" --file /tmp/t.jsonl
```

## 3. Ingest an unseen batch with the ingestion Job (≈ 2 min)
Batch C (`data/batch_c/`, one synthetic shuttle-service notice) has never been ingested.
```bash
kubectl apply -f k8s/a3/lake-drop-pod.yaml && kubectl wait -n rahbar --for=condition=Ready pod/lake-drop
kubectl cp data/batch_c/. rahbar/lake-drop:/data/lake/incoming/
kubectl delete pod lake-drop -n rahbar
kubectl create job --from=cronjob/reindex ingest-batch-c -n rahbar
kubectl wait -n rahbar --for=condition=complete job/ingest-batch-c --timeout=20m
kubectl logs -n rahbar job/ingest-batch-c | tail -25    # verification: 1 verified; sync: only its chunks embedded
make ask Q="When does the campus shuttle to Faizabad run?"   # cited answer from the new document
```
Ingest Batch C only at the demo. Do not rehearse with it, or it will no longer be unseen.

## If X fails, do Y
| Symptom | Fix |
|---|---|
| `kubectl` says "connection refused" or "no route to host" | `minikube start`, wait for it, then `kubectl get pods -n rahbar`. Afterwards check `kubectl get hpa -n rahbar` (next row). |
| HPA shows `<unknown>` | Right after a rollout this is normal: wait about 2 min while the new pods start. If it persists after a minikube restart: | `minikube ssh -- 'sudo crictl stop $(sudo crictl ps -q --name kube-controller-manager)'`, then wait about 1 min |
| Gemini 429 / quota in the api logs | Nothing to do: the Groq fallback is automatic (`GROQ_API_KEY` is in the Secret). The trace's `llm.provider` shows which provider answered. |
| Pod not Ready / CrashLoopBackOff | `kubectl describe pod <p> -n rahbar` (events) and `kubectl logs <p> -n rahbar --previous`. `/readyz` gives the reason (Chroma, Redis, embed pin). |
| `ErrImagePull` / `ImagePullBackOff` | The image is missing in minikube: `make images TAG=dev`. Never run `crictl rmi --prune` (it deletes unused images such as indexer/eval). |
| Ollama answers only on 127.0.0.1 (demo_check "Ollama listening" FAIL) | `sudo systemctl restart ollama` with `OLLAMA_HOST=0.0.0.0` in its unit (`systemctl edit ollama`), or `OLLAMA_HOST=0.0.0.0 ollama serve` |
| Eval Job `Failed` | `kubectl logs -n rahbar job/eval | tail -25`. A gate table means a real gate FAIL; a traceback means an infrastructure fault (check the baseline file and Ollama). |
| Job "field is immutable" on apply | `kubectl delete job <name> -n rahbar` and apply again |
