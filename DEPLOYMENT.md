# Deployment Guide

This guide covers containerization and Kubernetes deployment for LogPurifier.

## Docker

### Pre-built Images

Images are available at Aliyun Container Registry:

```
registry.cn-shanghai.aliyuncs.com/holgercloud/logexp-logpurifier:latest
```

### Build Locally

```bash
docker build -t logpurifier:local .
```

### Run with Docker

```bash
docker run --rm \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/artifacts:/app/artifacts \
  -v $(pwd)/logs:/app/logs \
  registry.cn-shanghai.aliyuncs.com/holgercloud/logexp-logpurifier:latest \
  --dataset BGL --window 300 --models IM OCSVM --run-id docker-test-v1
```

Mount points:
- `/app/data`: datasets (read-only)
- `/app/artifacts`: results and intermediate caches (read-write)
- `/app/logs`: log files (read-write)

Pass arguments after the image name; they go directly to `scripts/run_ad.py`.

**Recommendation**: Always specify `--run-id` in Docker/K8s to ensure deterministic paths and
enable cache reuse on retry. Without it, each container restart generates a new ID.

## Kubernetes

Deploy to Kubernetes for large-scale experiments. 110 pre-configured Jobs (3 datasets × 5 models × 7 windows + HDFS × 5 models)
in the `logexp` namespace. See [`k8s/README.md`](k8s/README.md) for complete guide (Chinese).

### Generate Job Manifests

When using a new image version, regenerate Job manifests:

```bash
# Use specific image tag (recommended)
python scripts/generate_k8s_jobs.py v0.1.0

# Or use latest (default)
python scripts/generate_k8s_jobs.py
```

This generates 110 Job YAML files under `k8s/jobs/`, all referencing the specified image tag.

### Quick Start

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Submit all 110 jobs
kubectl apply -f k8s/jobs/ -R

# Check status
kubectl get jobs -n logexp

# View logs (example)
kubectl logs -n logexp -f job/logexp-logpurifier-job-bgl-im-w300

# Results are written to NAS
ls /nas/logexp-data/reproduction-logpurifier/artifacts/
```

### NAS Mount Points

You may need to mount NAS (or any shared storage) at `/nas` in all Kubernetes nodes. The following paths are used in the Job manifests:

- `/app/data` → `/nas/LAD/Dataset` (datasets, read-only)
- `/app/artifacts` → `/nas/logexp-data/reproduction-logpurifier/artifacts` (results)
- `/app/logs` → `/nas/logexp-data/reproduction-logpurifier/logs` (log files)

### Job Matrix

- **Datasets**: BGL, Thunderbird, Spirit (line-based), HDFS (session-based)
- **Models**: IM, OCSVM, PCA, IForest, LogCluster
- **Windows**: 60, 100, 120, 300, 600, 1800, 3600 seconds (line-based only)
- **Total**: 110 Jobs
- **Timeout**: 24 hours per Job
- **Resources**: 2-4 CPU, 4-8Gi memory

### Selective Submission

```bash
# Single dataset
kubectl apply -f k8s/jobs/bgl/

# Single window across all datasets
kubectl apply -f k8s/jobs/*/*/*-w300.yaml

# Single model across all datasets and windows
kubectl apply -f k8s/jobs/*/*/*-ocsvm-*.yaml

# Single job
kubectl apply -f k8s/jobs/bgl/bgl-im-w300.yaml
```

### Available Manifests

| File | Purpose |
|------|---------|
| `k8s/namespace.yaml` | logexp namespace |
| `k8s/jobs/<dataset>/*.yaml` | 110 experiment Jobs organized by dataset |
| `k8s/README.md` | Full deployment guide (Chinese) |

## Architecture

### Dockerfile

- **Base**: `python:3.11-slim`
- **User**: non-root `logpurifier` (uid 1000)
- **Dependencies**: installed via `uv` (production only, no dev tools)
- **Entrypoint**: `uv run python scripts/run_ad.py`

### Volumes

- `/app/data`: mount datasets here
- `/app/artifacts`: results persist here (the CLI default `artifacts/` resolves here under WORKDIR `/app`)
- `/app/logs`: log output

### Security

- Runs as non-root user
- Read-only data mount recommended (`-v data:/app/data:ro`)
- No secrets or credentials in image
