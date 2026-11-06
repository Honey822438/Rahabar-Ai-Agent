# Engineering notes

<!-- STARTER-TODO(7): questions 5 and 7 are still to be answered. -->

## 1. Indexing in API startup: what breaks with 3 replicas and one Chroma volume?

**The failure:** three pods write to one Chroma at the same time. Our `store()` deletes the live collection and renames its build collection (`indexer/pipeline/store.py:41,57-58`). All three replicas would use the same `rahbar__build` name, so one pod's start would delete another's half-written build. The result is a crash, or an index no single run produced.

It also breaks restarts. A full index takes about 8.5 minutes, while `startupProbe` allows 30 × 2 = 60 seconds (`k8s/base/api.yaml:39-42`). If indexing blocked startup, the kubelet would kill every pod before it finished, and the loop would never end.

**The object that prevents it:** the Job at `k8s/base/indexer-job.yaml:2`, with `backoffLimit` at line 8 and `restartPolicy: OnFailure` at line 15. The CronJob adds `concurrencyPolicy: Forbid` (`k8s/base/reindex-cronjob.yaml:10`). The API's startup only reads metadata (`api/app/main.py:38-43`).


## 2. Readiness and liveness swapped, Chroma slow for 90 seconds: what happens?

This is reasoned from our manifest; we did not run it.

**As shipped:** liveness uses `/healthz`, which touches nothing (`k8s/base/api.yaml:43-46`, `api/app/routes/health.py:29-32`). Readiness uses `/readyz`, which calls Chroma (`api.yaml:47-51`, `health.py:41`). After 3 failures at 10-second intervals, about 30 seconds, pods leave the Service. Clients get errors from the Ingress, but no container restarts. When Chroma recovers, pods return within a probe period.

**Swapped:** liveness would call `/readyz` every 20 seconds, with 3 allowed failures (`api.yaml:45-46`). That reaches the limit at about 60 seconds, inside the 90-second slowdown, and the kubelet kills all 3 pods at about the same time. The default 1-second liveness timeout could trigger this even when Chroma is merely slow. Restarting fixes nothing, because Chroma is the problem, so pods can fall into `CrashLoopBackOff` and keep failing after Chroma recovers.

Meanwhile readiness on `/healthz` always passes, so the Service keeps sending traffic to pods that can't retrieve. A dependency problem has become an outage of the API itself.


## 3. What does a CPU-based HPA measure on a generation service, and what should scale it?

Our HPA targets 70% of the CPU request, which is 70m of 100m (`k8s/base/api.yaml:59,92`). While Gemini generates, the API is mostly waiting on a network call (`api/app/providers/llm/hosted.py:50-61`), so the CPU cost is low and the HPA sees almost nothing. It measures JSON parsing, cosine scans and logging, not the work users wait for.

So a pod can be full of slow requests while the HPA reads near idle: `docs/evidence/hpa.txt` shows 3% at rest. In our rollout test, cached traffic at 2 requests per second put two pods at 100m and 157m (`docs/evidence/kubectl-top.txt` shows the idle figures). That means cheap cached requests can trigger scaling more readily than expensive generation does. Adding pods also doesn't help with a provider rate limit, since all pods share one key.

**The better signal** is requests in flight per pod, or the queue wait, with generation latency alongside it.

**What we would need to build:**
1. An in-flight gauge in `api/app/services/telemetry.py`; today's metrics (lines 10-16) only cover completed work.
2. Prometheus to scrape `/metrics`.
3. `prometheus-adapter` or KEDA to expose it to the HPA.
4. A `Pods` metric in the HPA, replacing lines 88-92 of `api.yaml`.


## 4. The indexer's peak memory, its limit, the margin, and the exit code when it is wrong

**Peak:** 196 MiB on a full index with OCR (`docs/evidence/kubectl-top.txt`). `kubectl top` only showed a maximum of 177Mi when sampled every 5 seconds, so we also read the cgroup's `memory.peak`, which records the true high point.

**Limit:** 512Mi, with a 256Mi request (`k8s/base/indexer-job.yaml:61,64`, same in `k8s/base/reindex-cronjob.yaml:69`). We first guessed 1536Mi and lowered it after measuring.

**Margin:** 316 MiB, about 2.6× the peak, because OCR memory grows with scanned pages and a re-index may meet a larger corpus.

**If the limit is too low:** the kernel kills the process. The container reports `OOMKilled`, **exit code 137**. With `restartPolicy: OnFailure` the container restarts in the same pod, and `backoffLimit: 3` (lines 8 and 15) ends it as Failed. The old index stays live, because the swap happens only at the end (`indexer/pipeline/store.py:54-58`). We did not trigger an OOM on purpose. A request too high for the node gives a different symptom: the pod stays `Pending`, with no exit code.


## 5. recall@5 by question type: where is it worst, and why?

## 6. EMBED_MODEL changed on the API only: what does your system do?

We ran this; the output is in `docs/evidence/embed-pin-mismatch.txt`. The new pods stay `0/1`, and the old ones keep serving.

1. The indexer recorded its model in the collection metadata (`indexer/pipeline/store.py:43`).
2. The API reads `EMBED_MODEL` from the ConfigMap (`k8s/base/configmap.yaml:10`, `api/app/config.py:64`).
3. At startup and on each `/readyz` call, `embed_pin_conflict` compares them (`api/app/main.py:41`, `api/app/routes/health.py:17-26,44`).
4. On a mismatch it logs `refusing readiness: embedding model conflict` with both names, and `/readyz` returns 503 naming them.

Because `maxUnavailable: 0` (`k8s/base/api.yaml:13`), the rollout stalls: the old pods still serve, the bad pod gets no traffic, and no user sees wrong retrieval. Without this check, query vectors from one model would be compared with stored vectors from another. If the dimensions matched, that gives confident nonsense rather than an error.

**The caveat:** a ConfigMap change alone does nothing to running pods, because they read it at start. Pods restarted after the change hit the check; old pods keep working until replaced. If every pod is restarted at once, the service is down until the fix.

**The fix:** change `EMBED_MODEL`, re-index with the Job, and then restart the API, or revert the value.


## 7. The failure that cost us more than an hour
