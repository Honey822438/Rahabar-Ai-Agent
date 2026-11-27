#!/usr/bin/env bash
# F2 demo: the gate verdict changes after a ConfigMap edit, with no image rebuild.
# Run 1 = stock thresholds (expect PASS). Then raise faithfulness min to an impossible 1.01
# in the live ConfigMap and re-run the same eval Job (expect FAIL). Finally restore.
# Heavy (two eval Jobs, ~2x the eval time). Run alone, after the chain has finished.
set -euo pipefail
NS=rahbar
run_eval() {
  kubectl delete job eval -n $NS --ignore-not-found
  kubectl apply -f k8s/eval-job.yaml
  until kubectl get job eval -n $NS -o jsonpath='{.status.conditions[*].type}' | grep -qE 'Complete|Failed'; do sleep 20; done
  kubectl get job eval -n $NS
  kubectl logs -n $NS job/eval | grep -iE "gate|PASS|FAIL" | tail -15 || true
}
kubectl apply -f k8s/a3/gate-configmap.yaml
echo "=== 1) stock thresholds ==="; run_eval
echo "=== 2) edit ConfigMap: e2e.faithfulness min 0.9 -> 1.01 ==="
kubectl get configmap gate-config -n $NS -o yaml \
  | sed 's/{metric: e2e.faithfulness, kind: min, value: 0.9}/{metric: e2e.faithfulness, kind: min, value: 1.01}/' \
  | kubectl apply -f -
kubectl get configmap gate-config -n $NS -o yaml | grep -m1 "{metric: e2e.faithfulness"
run_eval
echo "=== 3) restore ==="; kubectl apply -f k8s/a3/gate-configmap.yaml
