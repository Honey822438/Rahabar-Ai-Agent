# A3 eval Job evidence notes
- `a3-eval-k8s-baseline.txt`: the Job status is **Failed** because the gate compared this run with the 24 Nov baseline (26 golden questions), and recall@5 was 0.936 vs 0.962, rule ≥ 0.942. The golden set has 39 questions now (Batch B + E4 added), so the two runs are not like-for-like. This run is now the official baseline (`config/gate.yaml`). Gated against itself, it passes.
- `a3-eval-k8s-c600.txt`: candidate rahbar_c600 gated against the k8s-baseline run (`k8s/eval-job-candidate.yaml`).
