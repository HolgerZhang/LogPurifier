#!/usr/bin/env python3
"""Generate K8s Job manifests for all dataset-model-window combinations."""

import sys

DATASETS = {
    "BGL": {"windows": [60, 100, 120, 300, 600, 1800, 3600]},
    "Thunderbird": {"windows": [60, 100, 120, 300, 600, 1800, 3600]},
    "Spirit": {"windows": [60, 100, 120, 300, 600, 1800, 3600]},
    "HDFS": {"windows": [0]},
}

MODELS = ["IM", "OCSVM", "PCA", "IForest", "LogCluster"]

TEMPLATE = """apiVersion: batch/v1
kind: Job
metadata:
  name: logexp-logpurifier-job-{dataset_lower}-{model_lower}-w{window}
  namespace: logexp
  labels:
    app: logexp-logpurifier
    component: experiment
    dataset: {dataset_lower}
    model: {model_lower}
    window: "w{window}"
spec:
  activeDeadlineSeconds: 86400  # 24 hours
  backoffLimit: 0
  template:
    metadata:
      labels:
        app: logexp-logpurifier
        component: experiment
        dataset: {dataset_lower}
        model: {model_lower}
        window: "w{window}"
    spec:
      restartPolicy: Never

      containers:
      - name: logexp-logpurifier-pod-{dataset_lower}-{model_lower}-w{window}
        image: registry.cn-shanghai.aliyuncs.com/holgercloud/logexp-logpurifier:{image_tag}
        args:
          - "--dataset"
          - "{dataset}"
          - "--window"
          - "{window}"
          - "--models"
          - "{model}"
          - "--artifacts"
          - "/app/artifacts"
          - "--run-id"
          - "{dataset_lower}-{model_lower}-w{window}"
          - "--log-level"
          - "DEBUG"

        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"

        volumeMounts:
        - name: data
          mountPath: /app/data
          readOnly: true
        - name: artifacts
          mountPath: /app/artifacts
        - name: logs
          mountPath: /app/logs

        env:
        - name: PYTHONUNBUFFERED
          value: "1"

      volumes:
      - name: data
        hostPath:
          path: /nas/LAD/Dataset
          type: Directory
      - name: artifacts
        hostPath:
          path: /nas/logexp-data/reproduction-logpurifier/artifacts
          type: DirectoryOrCreate
      - name: logs
        hostPath:
          path: /nas/logexp-data/reproduction-logpurifier/logs
          type: DirectoryOrCreate
"""

def main():
    from pathlib import Path

    image_tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    jobs_base = Path("k8s/jobs")

    # Clear existing
    if jobs_base.exists():
        import shutil
        shutil.rmtree(jobs_base)

    total = 0
    max_job = ""
    max_len = 0

    for dataset, config in DATASETS.items():
        dataset_dir = jobs_base / dataset.lower()
        dataset_dir.mkdir(parents=True, exist_ok=True)

        for model in MODELS:
            for window in config["windows"]:
                content = TEMPLATE.format(
                    dataset=dataset,
                    dataset_lower=dataset.lower(),
                    model=model,
                    model_lower=model.lower(),
                    window=window,
                    image_tag=image_tag,
                )
                out = dataset_dir / f"{dataset.lower()}-{model.lower()}-w{window}.yaml"
                out.write_text(content)

                job_name = f"logexp-logpurifier-job-{dataset.lower()}-{model.lower()}-w{window}"
                if len(job_name) > max_len:
                    max_len = len(job_name)
                    max_job = job_name

                total += 1

    print(f"Generated {total} Jobs with image tag: {image_tag}")
    print(f"Longest: {max_job} ({max_len} chars)")

if __name__ == "__main__":
    main()
