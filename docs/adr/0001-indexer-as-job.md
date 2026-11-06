# ADR 0001: The indexer runs as a Job, not at API startup

## Status
Accepted · 6 Nov 2026

## Context
We run 3 API replicas and one Chroma volume. A full index of our corpus takes about 8.5 minutes, because 41 pages need OCR and every chunk goes through Ollama on a CPU. Indexing at API startup looks simple, but four things go wrong:

1. **Writers race.** Three pods write to one Chroma at once, so the index matches no single run.
2. **Every restart pays again.** A rollout, an OOMKill or a node drain would each repeat the 8.5 minutes. Our measured rollout took under a minute.
3. **Readiness stops being honest.** The pod either reports ready with no index, or stays unready past its startup budget and gets killed. Our `startupProbe` allows 60 seconds (`k8s/base/api.yaml:39-42`), far less than 8.5 minutes.
4. **Re-indexing needs a redeploy.** A corpus update should not need a new API rollout.

## Decision
Only a Kubernetes Job (`k8s/base/indexer-job.yaml:2`) and a weekly CronJob with the same image and arguments (`k8s/base/reindex-cronjob.yaml`) write to Chroma. The API only reads. Its `/readyz` returns 503 until the collection exists, is non-empty and matches the embedding pin (`api/app/routes/health.py:35-56`).

A re-index needs one command and no redeploy:

```bash
kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar
```

`restartPolicy: OnFailure` and `backoffLimit: 3` retry failures. `concurrencyPolicy: Forbid` stops scheduled runs overlapping (`k8s/base/reindex-cronjob.yaml:10`). The Job builds a separate collection and renames it only after checking the count (`indexer/pipeline/store.py:40-58`), so a Job that dies midway leaves the old index in place.

## Options considered
- **Index at startup with a lock.** Stops the race, but restarts still pay the cost and readiness is still wrong.
- **Init container on the API.** Same problems, and it runs once per replica.
- **Build the index into an image.** Corpus changes would need an image rebuild and redeploy, and Chroma is a separate stateful service anyway.

## Consequences
- API pods start in seconds and restart cheaply.
- A fresh cluster serves nothing until the first Job finishes. This is intended and visible as 503 on `/readyz`.
- The swap deletes the old collection and then renames the new one (`store.py:57-58`), so `/readyz` and retrieval can fail for that brief moment. A manual re-index does not rule this out; we accept it for a small service and would watch it through the failure counters.
- `concurrencyPolicy` does not cover a manual Job started during a scheduled run, so operators must check first.
