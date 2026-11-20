from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(dag_id="my_first", start_date=datetime(2024, 1, 1), schedule=None, catchup=False, tags=["edu"]) as dag:
    hello = BashOperator(task_id="hello", bash_command='echo "hello from $(hostname)"')
    bye = BashOperator(task_id="bye", bash_command='echo "bye"'
    hello >> bye
