# 06. Pod가 Running인데 DAG가 멈췄다면 — Prometheus와 Grafana

모니터링에는 두 질문이 있다. **① Kubernetes가 컨테이너를 준비했나? ② Airflow가 작업을 처리하나?** 이 클러스터의 Prometheus에서 기존 `airflow` namespace의 Pod/CPU/재시작 지표는 조회할 수 있지만, 조회 당시 기존 scheduler의 StatsD가 꺼져 있어 Airflow 애플리케이션 시계열은 없었다. 공용 Airflow를 변경하지 말고 두 신호를 따로 확인한다.

## 1. 지금 볼 수 있는 Kubernetes 신호

**Prometheus → Query** 또는 **Grafana → Explore → Prometheus 데이터 소스 → Code**에서 아래 쿼리를 **한 번에 하나씩** 실행한다. 기존 설치를 관찰할 때는 `namespace="airflow"`, 새 교육 앱을 배포한 후에는 `namespace="edu-platform-lab"`을 쓴다. 읽기 전용으로 충분하다.

```promql
sum by (phase) (kube_pod_status_phase{namespace="airflow"})
```
```promql
sum by (pod) (increase(kube_pod_container_status_restarts_total{namespace="airflow"}[15m]))
```
```promql
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="airflow",container!="",container!="POD"}[5m]))
```
```promql
kube_deployment_status_replicas_available{namespace="airflow",deployment="airflow-scheduler"}
```

교육 quota가 설치됐을 때 `kube_resourcequota{namespace="edu-platform-lab",resource="pods"}`의 `type="used"`와 `type="hard"`를 비교한다. Phase `Running`과 컨테이너 `Ready`는 다르다. CPU 쿼리의 단위는 코어이며 퍼센트가 아니다.

## 2. Airflow 전용 지표가 생기는 경로

GitOps 저장소의 [`metrics.yaml`](https://github.com/kyeongseooh/k8s-platform-gitops/blob/main/clusters/training/metrics.yaml)에는 exporter 설정·Deployment·Service·ServiceMonitor가 있다. `airflow.yaml`은 StatsD를 켜고 **UDP 9125**로 보낸다. exporter는 **TCP 9102 `/metrics`**로 노출한다. Prometheus Operator가 ServiceMonitor를 읽고, Prometheus가 그 URL을 주기적으로 scrape한다. Grafana는 Prometheus를 쿼리할 뿐 직접 Pod를 긁지 않는다.

| 어디서 | 확인할 값 |
|---|---|
| Airflow | StatsD host `edu-statsd`, UDP 9125, prefix `airflow` |
| exporter | `airflow.scheduler_heartbeat` → `edu_airflow_scheduler_heartbeat_total`; `airflow.ti_successes`/`ti_failures` → `edu_airflow_task_instance_result_total{result="success"/"failure"}` |
| ServiceMonitor | **같은 namespace**의 Service label `app.kubernetes.io/name=edu-statsd` 선택, endpoint `port: metrics`는 **Service 포트 이름** |
| Prometheus | **Status → Targets**에서 `edu-airflow-metrics` 검색. 이 설치는 ServiceMonitor/namespace 선택자가 `{}`이고, 다른 환경은 릴리스 라벨 요구 가능 |

```bash
# 02장의 교육 앱을 설치한 경우에만
k get svc,deploy,servicemonitor -l app.kubernetes.io/name=edu-statsd
k logs deploy/edu-statsd --tail=30
# 교육용 smoke 신호. scheduler heartbeat나 실패 횟수를 인위적으로 만들지 않는다.
k exec deploy/edu-airflow -- python -c 'import socket; socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto(b"edu_smoke_test:1|c",("edu-statsd",9125))'
k exec deploy/edu-airflow -- python -c 'import urllib.request; text=urllib.request.urlopen("http://edu-statsd:9102/metrics",timeout=4).read().decode();print([r for r in text.splitlines() if r.startswith("edu_smoke_test ")])'
```

최소 한두 번의 scrape 주기 후 아래 쿼리를 각각 실행한다. 교육 DAG를 실행하지 않았다면 task result 시계열이 아직 없을 수 있다.

```promql
up{namespace="edu-platform-lab",service="edu-statsd"}
```
```promql
increase(edu_airflow_scheduler_heartbeat_total{namespace="edu-platform-lab"}[5m])
```
```promql
sum by (result) (increase(edu_airflow_task_instance_result_total{namespace="edu-platform-lab"}[15m]))
```

## 3. Grafana에서 개인 화면 만들기

**Explore → Prometheus → Run query → Table**에서 실제 label과 값을 먼저 확인한다. 시간 범위는 Last 30 minutes로 시작한다. 개인 폴더에 쓰기 권한이 있다면 **Dashboards → New → Add visualization**에서 같은 소스를 고른다. 공용 대시보드는 수정하지 않는다.

- `exporter를 긁을 수 있나?`는 `up`의 현재값을 **Stat**으로 표시한다. 1=UP, 0=DOWN, 데이터 없음=대상 없음으로 **문자도** 표시한다.
- `최근 15분 작업 결과`는 task `increase` 쿼리를 **Time series**로 표시한다. 범례를 `{{result}}`로 두고 표에서도 success/failure를 읽을 수 있게 한다. 카운터의 `increase`는 조회 구간 경계에서 추정치이므로 개별 run의 정확한 이력은 Airflow task log에서 확인한다.
- CPU(코어)와 작업 횟수는 단위가 다르므로 별도 패널을 사용한다. 패널이 비어도 무조건 0으로 채우지 않는다.

## 장애 과제: 빈 그래프를 세 갈래로 나누기

Explore 쿼리의 namespace만 고의로 잘못 입력해 **No data**를 확인한 뒤 원래 값으로 회복한다. 실제 대상이나 공용 모니터 설정을 지울 필요가 없다.

| 증거 | 의미와 다음 행동 |
|---|---|
| Targets에 없음 | ServiceMonitor가 선택됐는가? Service 라벨·포트 이름·namespace 확인 |
| 타깃은 있지만 `up=0` | scrape는 시도했으나 실패. Targets의 Last error, endpoint Ready, 네트워크 확인 |
| `up=1`, smoke는 보이나 heartbeat 증가 없음 | exporter까지는 정상. scheduler 로그, StatsD 설정, 매핑, UDP 통신 확인 |
| heartbeat는 증가하지만 task 실패 | 해당 run의 Airflow 로그·task Pod Events 확인. `ImagePullBackOff`와 계산 오류는 원인이 다르다. |

[검증 기록](../verification.md)에는 실제 클러스터 쿼리와 격리된 Docker에서 확인한 scheduler heartbeat를 구분했다. 플랫폼 관리자가 실습용 Application을 등록하기 전에는 그 namespace에서 `up=1`을 기대하지 않는다.
