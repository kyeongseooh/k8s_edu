"""Launch an isolated, digest-pinned training task. See platform/docs/04-airflow.md."""
from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.models.dag import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

TASK_IMAGE = os.environ["TASK_IMAGE"]
TASK_NAMESPACE = os.environ.get("TASK_NAMESPACE", "edu-platform-lab")
TASK_SERVICE_ACCOUNT = os.environ.get("TASK_SERVICE_ACCOUNT", "edu-task")
TASK_IMAGE_PULL_SECRET = os.environ.get("TASK_IMAGE_PULL_SECRET", "edu-harbor-pull")

with DAG(
    dag_id="edu_image_report",
    description="Launch the edu report-image task Pod via KubernetesPodOperator",
    schedule=None,  # manual trigger only; this is an instructor-driven lab
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["edu", "kpo", "lab"],
) as dag:
    run_report = KubernetesPodOperator(
        task_id="run_report",
        name="edu-image-report",
        namespace=TASK_NAMESPACE,
        image=TASK_IMAGE,
        # Entrypoint is already baked into the image; no cmds/arguments.
        service_account_name=TASK_SERVICE_ACCOUNT,
        image_pull_secrets=[k8s.V1LocalObjectReference(name=TASK_IMAGE_PULL_SECRET)],
        in_cluster=True,
        get_logs=True,
        log_events_on_failure=True,
        on_finish_action="delete_pod",  # request cleanup on finish
        startup_timeout_seconds=120,
        execution_timeout=timedelta(minutes=5),
        container_resources=k8s.V1ResourceRequirements(
            requests={"cpu": "20m", "memory": "32Mi"},
            limits={"cpu": "100m", "memory": "96Mi"},
        ),
        # No automounted token on the task Pod (ServiceAccount edu-task has
        # automountServiceAccountToken: false); nothing extra to set here.
        labels={
            "app.kubernetes.io/part-of": "edu-platform-lab",
            "app.kubernetes.io/component": "edu-task",
        },
    )
