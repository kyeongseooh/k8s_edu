# 04. DAG가 내가 빌드한 이미지로 Pod를 실행하게 하기

**Airflow 이미지는 지휘자, 작업 이미지는 연주자다.** 교육 scheduler는 `apache/airflow:2.10.4`로 동작한다. DAG의 `KubernetesPodOperator`(KPO)가 [01장](01-image-harbor.md)의 **다른 이미지**로 일회용 Pod를 만들고 stdout을 task log에 옮긴다. scheduler 이미지 안에 작업 코드를 덮어쓸 필요가 없다.

| | 새 교육 배포 `edu-airflow` | 기존 `airflow` 배포 |
|---|---|---|
| 프로세스·DB | scheduler 1개, SequentialExecutor + SQLite/emptyDir | CeleryExecutor, scheduler/webserver/worker, Redis와 PostgreSQL |
| DAG 공급 | Git `dags/report.py` → hash 붙은 ConfigMap → Pod 템플릿 갱신 | git-sync가 DAG 소스 갱신 |
| 조작·이력 | 교육 namespace에서 CLI, Pod 교체 시 이력·로그 리셋 | 웹 UI 사용, DB·로그 보존 정책 별도 |
| 메트릭 | 별도 StatsD exporter로 전송하도록 선언 | 조회 당시 StatsD 비활성 |

## 1. 이미지와 DAG 연결 확인

GitOps 저장소에서 `clusters/training/task-image.properties`의 `image=` 값이 실제 Harbor digest인지 확인한다. `kubectl kustomize clusters/training`을 하면 이 파일과 `dags/report.py`가 **각각 내용 hash를 가진 ConfigMap**이 된다. Deployment의 `configMapKeyRef`와 볼륨 참조도 바뀌므로 Argo 동기화 후 **새 scheduler Pod**가 올바른 `TASK_IMAGE`를 받는다. 고정 이름 ConfigMap의 값만 고치면 실행 중인 프로세스의 환경변수는 갱신되지 않는다는 차이가 중요하다.

[DAG 소스](../examples/dags/report.py)의 핵심은 `image=TASK_IMAGE`, `namespace=TASK_NAMESPACE`, `service_account_name='edu-task'`, `image_pull_secrets=[…]`다. scheduler SA는 자기 namespace의 Pod를 만들고 로그를 읽을 수 있지만 task SA에는 RoleBinding도 API 토큰도 없다. 작업에는 credentials가 아니라 계산할 코드만 필요하다. 단, Pod를 생성할 수 있는 주체는 그 namespace의 다른 Secret을 마운트하는 Pod도 요청할 수 있다. 따라서 DAG 작성·머지 권한을 신뢰된 사람으로 제한하고, 교육 namespace에 다른 팀의 비밀을 함께 두지 않는다.

## 2. 첫 DAG 실행 — 교육 namespace만

[02장](02-gitops.md)의 앱 동기화와 pull Secret 등록이 끝난 뒤 실행한다. 먼저 스케줄러 프로세스 기동과 **DAG 파싱 완료**를 따로 확인한다. DAG 목록에 없다면 import error부터 본다.

```bash
air() { k exec deploy/edu-airflow -c airflow -- airflow "$@"; }
air dags list-import-errors
air dags list | grep edu_image_report
air dags unpause edu_image_report
RUN="manual__edu_$(date -u +%Y%m%dT%H%M%SZ)"
air dags trigger --run-id "$RUN" edu_image_report
air tasks states-for-dag-run edu_image_report "$RUN"
```

잠시 뒤 `states-for-dag-run`을 다시 실행한다. 다른 터미널에서 같은 namespace의 `k get pods -l app.kubernetes.io/component=edu-task -w`로 transient Pod를 볼 수 있다(Ctrl+C로 종료). KPO가 완료 Pod 삭제를 요청하므로 **목록이 비었다는 것 자체는 성공 증거가 아니다.** 기본 로컬 로그 템플릿에서는 아래 경로를 확인한다.

```bash
k exec deploy/edu-airflow -c airflow -- grep -F 'report_ok rows=3 total=42' "/opt/airflow/logs/dag_id=edu_image_report/run_id=$RUN/task_id=run_report/attempt=1.log"
```

성공은 **같은 run ID에서 task 상태 `success` + 계산 결과 42**다. 재시도했다면 `attempt=2.log`처럼 번호가 바뀐다. 기존 웹 UI를 사용할 때는 해당 DAG → **Grid → 동일 run/task → Logs**에서 같은 근거를 찾는다. 교육 배포는 공용 UI에 등록되지 않으며 별도 웹 서버도 열지 않는다.

## 3. 장애 과제: 이미지는 받아졌지만 작업 자체가 실패했다

개인 실습 브랜치의 `dags/report.py`에서 KPO에 `arguments=['--amounts', '1,bad']`를 추가해 커밋하고 교육 앱이 보는 브랜치에 반영한다. scheduler 롤아웃이 끝나면 위 절차로 새 run ID를 사용한다. **이미지 pull 실패**라면 task 컨테이너가 아직 시작하지 않아 Pod Events에 `ErrImagePull` 등이 보인다. 이번 경우에는 컨테이너가 시작했고 task log에 `amounts must be comma-separated integers`와 nonzero 종료가 남아야 한다. 변경 커밋을 revert하고 새 run에서 42를 확인한다. 실습 후 DAG를 멈추려면 `air dags pause edu_image_report`. 실제 운영에서 DB migration이나 이미 쓴 S3 객체는 `git revert`가 되돌려 주지 않는다.

## 4. 운영형: 공식 Helm chart와 Git values 연결

기존 설치를 다시 만들지 않는다. 아래는 **별도 환경 설계용** Application `spec.sources` 조각이다. chart 버전과 Airflow 이미지 버전은 별도로 고정한다. 운영자 AppProject에서 두 소스 모두를 승인해야 한다.

```yaml
sources:
- repoURL: https://airflow.apache.org
  chart: airflow
  targetRevision: 1.16.0
  helm:
    valueFiles: ['$values/environments/training/values.yaml']
- repoURL: https://git.example.invalid/team/airflow-values.git
  targetRevision: main
  ref: values
```

values 저장소에는 `defaultAirflowTag: 2.10.4`, `airflowVersion: 2.10.4`, `executor: CeleryExecutor`, `dags.gitSync` repo/branch/subPath, 외부 DB·broker **Secret 참조** 등을 둔다. 실제 DB 연결 문자열·Fernet key·webserver secret은 별도 관리한다. 차트 교체 전: 같은 chart 버전으로 `helm template` → migration/job 및 hook 설정 검토 → DB 백업/복구 가능성 확인 → scheduler/worker가 같은 DAG revision을 읽는지 확인한다. 교육용 SQLite 구성은 운영 백업·고가용성을 제공하지 않는다.
