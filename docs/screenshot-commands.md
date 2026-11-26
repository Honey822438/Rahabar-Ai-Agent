# Screenshot commands (A3 Submission list)

Run from the repo root with the venv active (`source .venv/bin/activate`) and host Ollama up.
**WAIT** = needs the c600 / baseline / candidate eval chain to have finished (and the cluster up).
**NOW** = uses results already on disk. One heavy job at a time.

## A. Verification + incremental rerun  (NOW, local lake)
```bash
cat "$(ls -t eval/results/verification-*.txt | head -1)"        # A1: Batch B verification report
cd indexer && LAKE_DIR=../data/lake OLLAMA_URL=http://localhost:11434 \
  python -m pipeline.sync 2>&1 | tail -8; cd ..                    # A2: unchanged corpus -> 0 chunks embedded
```
In-cluster version (WAIT): `kubectl create job --from=cronjob/reindex reindex-shot -n rahbar && kubectl wait -n rahbar --for=condition=complete job/reindex-shot --timeout=30m && kubectl logs -n rahbar job/reindex-shot | tail -30`

## B. Suite summary, all 3 levels  (WAIT for the baseline run of the chain)
```bash
kubectl logs -n rahbar job/eval | sed -n '/SUMMARY/,$p'          # or the local run:
python eval/compare.py "$(ls -t eval/results/*-baseline.json | head -1)"
```

## C. Gate fail + gate pass  (NOW from saved runs; WAIT for the fresh chain run)
```bash
python eval/gate.py "$(ls -t eval/results/*-candidate-c600.json | head -1)"; echo "exit=$?"         # PASS, exit 0
python eval/gate.py "$(ls -t eval/results/*-candidate-c100-bad.json | head -1)"; echo "exit=$?"     # FAIL, exit 1
```

## D. One trace + prompt rebuild  (NOW)
```bash
grep 2f213c99a8ea41e597f4a678946f98e3 data/traces/traces.jsonl | python -m json.tool | head -60   # D1 full record
python -m tools.trace 2f213c99a8ea41e597f4a678946f98e3 --file data/traces/traces.jsonl; echo "exit=$?"   # D2 rebuild, hash OK = exit 0
```

## E. Coverage before / after  (NOW, ~1 min of embeddings)
```bash
python - <<'P'                                   # golden set without the E4 additions
import json; ids={json.loads(l)["id"] for l in open("eval/drafts/e4_golden.jsonl") if l.strip()}
open("/tmp/golden-before-e4.jsonl","w").writelines(l for l in open("eval/golden.jsonl") if l.strip() and json.loads(l)["id"] not in ids)
P
python eval/coverage.py --golden /tmp/golden-before-e4.jsonl --label before-e4; echo "exit=$?"   # 0.60, exit 1
python eval/coverage.py --label after-e4; echo "exit=$?"                                       # exit 0
```

## F. Kubernetes  (all WAIT: cluster up, chain finished)
```bash
kubectl get all,pvc,configmap,cronjob,job -n rahbar                          # F1
kubectl logs -n rahbar job/indexer | tail -30                                # completed ingest Job
kubectl logs -n rahbar job/eval | tail -25                                   # completed eval Job
scripts/demo/f2_configmap_gate.sh                                            # F2 verdict changes after ConfigMap edit (heavy: 2 evals)
scripts/demo/f3_rollout_undo.sh                                              # F3 rollout status + undo + trace with previous collection
scripts/demo/f4_metrics.sh                                                   # F4 /metrics
kubectl top pods -n rahbar                                                   # F5 requests/limits evidence
```
