"""Harbor에 올린 내 이미지를 작업으로 실행하는 DAG.

KubernetesPodOperator는 "이 이미지로 Pod를 하나 띄워서 끝날 때까지 기다려라"는 작업이다.
Airflow 이미지에 내 코드나 라이브러리를 넣지 않아도 된다. 작업은 작업 전용 이미지 안에서 돈다.
"""
from datetime import datetime

from airflow import DAG
from airflow.models.param import Param
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

with DAG(
    dag_id="harbor_report",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["edu"],
    params={"amounts": Param("10,20,12", type="string", description="쉼표로 구분한 숫자")},
) as dag:
    KubernetesPodOperator(
        task_id="report",
        name="report",                                   # 만들어질 Pod 이름의 앞부분
        namespace="edu-airflow",
        image="harbor.10.0.1.230.nip.io/edu/report:v1",  # 01장과 같은 방법으로 올린 이미지
        image_pull_secrets=[k8s.V1LocalObjectReference("harbor-pull")],
        arguments=["--amounts", "{{ params.amounts }}"],  # 실행할 때 입력한 값이 들어간다
        get_logs=True,                                   # 작업 Pod의 출력을 Airflow 로그로 가져온다
        startup_timeout_seconds=90,                      # 90초 안에 Pod가 시작하지 못하면 실패 처리
        on_finish_action="delete_pod",                   # 끝나면 Pod를 지운다
        container_resources=k8s.V1ResourceRequirements(
            requests={"cpu": "50m", "memory": "32Mi"},
            limits={"cpu": "200m", "memory": "64Mi"},
        ),
    )
