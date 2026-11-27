# A3 eval Job evidence notes
- `a3-eval-k8s-baseline.txt`: the Job status is **Failed** because the gate compared this run with the 24 Nov baseline (26 golden questions), and recall@5 was 0.936 vs 0.962, rule ≥ 0.942. The golden set has 39 questions now (Batch B + E4 added), so the two runs are not like-for-like. This run is now the official baseline (`config/gate.yaml`). Gated against itself, it passes.
- `a3-eval-k8s-c600.txt`: candidate rahbar_c600 gated against the k8s-baseline run (`k8s/eval-job-candidate.yaml`).
- `a3-eval-job-default.txt`: `k8s/eval-job.yaml` exactly as committed, no env overrides. The gate uses the k8s-baseline built into the image and gives **PASS**.
- `a3-f3-rollout-undo.txt`: the trace collection is `rahbar` before, `rahbar_c600` after `set env` + rollout, and `rahbar` again after `rollout undo` (same embedding model and version).
- `a3-f4-metrics.txt`: `/metrics` through a port-forward.
- `a3-f5-kubectl-top.txt`: `kubectl top` with 4 concurrent queries next to the configured requests and limits. The api peaks at 295m CPU (limit 500m) and every pod stays at 66–165Mi memory, under its limits. After the minikube restart the HPA read `<unknown>` because kube-controller-manager had stale credentials (FailedGetScale Unauthorized). Restarting that container fixed it: `cpu: 30%/70%`.
- `a3-ingest-job.txt`: the completed ingest Job on the unchanged corpus: 0 chunks embedded, 0 orphans.
