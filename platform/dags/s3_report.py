"""작업 결과를 MinIO(S3)에 파일로 저장하는 DAG.

작업 Pod는 끝나면 사라진다. 결과물을 남기려면 Pod 바깥의 저장소에 써야 한다.
접속 정보(Access Key)는 Secret "s3-cred"에서 환경변수로 받는다. DAG 코드에는 비밀 값이 없다.
"""
from datetime import datetime

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

with DAG(
    dag_id="s3_report",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["edu"],
) as dag:
    KubernetesPodOperator(
        task_id="write_report",
        name="s3-report",
        namespace="edu-airflow",
        image="amazon/aws-cli:2.17.0",
        cmds=["sh", "-c"],
        arguments=[
            'echo "run={{ run_id }} generated_at=$(date -u +%FT%TZ) total=42" > /tmp/report.txt && '
            "aws s3 cp /tmp/report.txt s3://edu-lab/reports/{{ ds }}/{{ ts_nodash }}.txt && "
            "aws s3 ls s3://edu-lab/reports/ --recursive"
        ],
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-cred"))],
        env_vars={"AWS_ENDPOINT_URL": "http://10.0.1.185:9555", "AWS_DEFAULT_REGION": "us-east-1"},
        get_logs=True,
        startup_timeout_seconds=180,
        on_finish_action="delete_pod",
    )
