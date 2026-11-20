"""가장 단순한 DAG: 작업 3개를 순서대로 실행한다.

KubernetesExecutor에서는 아래 작업 하나하나가 별도의 Pod로 실행된다.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


def transform():
    numbers = [3, 14, 15, 9, 26]
    print(f"numbers={numbers} sum={sum(numbers)} max={max(numbers)}")
    return sum(numbers)


with DAG(
    dag_id="hello_k8s",
    start_date=datetime(2024, 1, 1),
    schedule=None,              # 자동으로 돌지 않는다. 화면에서 직접 실행한다
    catchup=False,
    tags=["edu"],
) as dag:
    extract = BashOperator(
        task_id="extract",
        bash_command='echo "extract: running on pod $(hostname)"; sleep 10',
    )
    transform_task = PythonOperator(task_id="transform", python_callable=transform)
    load = BashOperator(
        task_id="load",
        bash_command='echo "load: running on pod $(hostname)"; sleep 5; echo done',
    )

    extract >> transform_task >> load      # 실행 순서
