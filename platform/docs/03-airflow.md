# 03. Airflow 설치 — Argo CD와 Helm으로 Airflow 만들기

**이 장을 마치면**

- Airflow가 무엇이고, 쿠버네티스 위에서 어떤 Pod들로 이루어지는지 설명할 수 있습니다.
- Helm 차트와 Git의 설정 파일을 합쳐 Argo CD로 Airflow를 설치할 수 있습니다.
- Git의 설정을 고쳐서 Airflow를 바꿀 수 있습니다.

---

## 1. Airflow란

**Airflow**는 "작업을 정해진 순서대로, 정해진 시간에 실행"해 주는 도구입니다. 기초 과정 [18장](../../docs/18-batch.md)의 CronJob이 "작업 하나를 주기적으로" 실행했다면,
Airflow는 **여러 작업을 순서대로 엮어서** 실행합니다. 예를 들면 "데이터 추출 → 가공 → 적재 → 완료 알림"입니다.

| 용어 | 뜻 |
|---|---|
| **DAG** | 작업들과 그 실행 순서를 적은 것. Python 파일로 만든다 |
| **Task** | DAG 안의 작업 하나 |
| **DAG Run** | DAG를 한 번 실행한 것 |
| **Scheduler** | 실행할 때가 된 작업을 찾아 실행시키는 구성 요소 |
| **Webserver** | 화면(UI) |
| **Executor** | 작업을 "어디에서 어떻게" 실행할지 정하는 방식 |

### 쿠버네티스 위의 Airflow

![Airflow 구조](../../images/platform/p03-airflow.svg)

이 실습에서는 **KubernetesExecutor**를 씁니다. 작업(task) 하나가 실행될 때마다 **Pod를 하나 새로 띄우고, 끝나면 지웁니다.**

| Executor | 작업이 실행되는 곳 | 특징 |
|---|---|---|
| CeleryExecutor | 항상 떠 있는 worker Pod | 작업 시작이 빠르다. worker가 계속 자원을 차지한다 (공용 `airflow`가 이 방식) |
| **KubernetesExecutor** | 작업마다 새로 뜨는 Pod | 작업이 없으면 자원을 쓰지 않는다. 작업마다 Pod를 띄우는 시간이 든다 |

## 2. 설치 방법: Helm 차트 + Git + Argo CD

Airflow를 띄우려면 Deployment, Service, ConfigMap, Secret, Job, ServiceAccount, Role 등 리소스가 20개 넘게 필요합니다. 이것을 직접 쓰지는 않습니다.

**Helm 차트**는 이런 YAML 묶음을 "설정값만 넣으면 완성되는 틀"로 만들어 배포하는 방식입니다. Airflow 프로젝트가 공식 차트를 제공합니다.
우리는 **설정값 파일(`values.yaml`)만** 준비하면 됩니다.

![재료가 오는 곳](../../images/platform/p03-sources.svg)

| 재료 | 어디에 있나 | 내용 |
|---|---|---|
| Helm 차트 | `https://airflow.apache.org` | Airflow를 설치하는 틀 (우리가 고치지 않는다) |
| [values.yaml](../gitops/airflow/values.yaml) | 내 Git 저장소 | 이 Airflow를 어떻게 설정할지 |
| [postgres.yaml](../gitops/airflow/manifests/postgres.yaml) | 내 Git 저장소 | Airflow가 쓸 데이터베이스 |

[02장](02-argocd.md)에서는 Application의 출처(`source`)가 Git 디렉터리 하나였습니다. 이번에는 **출처가 여러 개**입니다. ([examples/argocd/app-airflow.yaml](../examples/argocd/app-airflow.yaml))

```yaml
spec:
  destination:
    server: https://kubernetes.default.svc
    namespace: edu-airflow
  sources:                                     # 출처가 세 군데다
  # 1) Airflow 공식 Helm 차트 (설치 방법)
  - repoURL: https://airflow.apache.org
    chart: airflow
    targetRevision: 1.16.0
    helm:
      releaseName: airflow
      valueFiles:
      - $values/platform/gitops/airflow/values.yaml     # 3)의 Git 저장소에 있는 설정 파일
  # 2) Git 저장소의 일반 YAML (PostgreSQL)
  - repoURL: https://github.com/kyeongseooh/k8s_edu.git
    targetRevision: main
    path: platform/gitops/airflow/manifests
  # 3) Git 저장소를 "$values"라는 이름으로 참조 (1에서 설정 파일을 읽기 위해)
  - repoURL: https://github.com/kyeongseooh/k8s_edu.git
    targetRevision: main
    ref: values
```

### values.yaml 읽어 보기

전체는 [파일](../gitops/airflow/values.yaml)에 주석과 함께 있습니다. 중요한 부분만 봅니다.

```yaml
executor: KubernetesExecutor          # 작업마다 Pod를 띄운다

data:
  metadataSecretName: airflow-metadata        # DB 접속 문자열이 든 Secret (kubectl로 미리 만든다)
fernetKeySecretName: airflow-fernet-key       # 암호화 키도 Secret에서 읽는다

ingress:
  web:
    enabled: true
    ingressClassName: nginx
    hosts:
    - name: edu-airflow.10.0.1.230.nip.io     # 접속 주소

dags:
  gitSync:
    enabled: true
    repo: https://github.com/kyeongseooh/k8s_edu.git
    branch: main
    subPath: platform/dags                    # 저장소 안에서 DAG 파일이 있는 디렉터리

logs:
  persistence:
    enabled: true                             # 작업 Pod가 사라져도 로그가 남도록 PVC에 저장
    storageClassName: nfs-client
```

기초 과정에서 배운 것들이 그대로 보입니다. Secret([05장](../../docs/05-secret.md)), Ingress([10장](../../docs/10-ingress.md)), PVC([06장](../../docs/06-pv-pvc.md)).

## 3. 실습 ① — 준비: 네임스페이스와 Secret

Airflow에 필요한 비밀 값들은 **Git에 넣지 않고** 직접 만듭니다. 값은 무작위로 생성합니다.

```bash
kubectl create namespace edu-airflow

DB_PW=$(openssl rand -hex 12)

# 1) PostgreSQL이 사용할 DB 이름·계정·비밀번호
kubectl -n edu-airflow create secret generic airflow-db \
  --from-literal=POSTGRES_DB=airflow \
  --from-literal=POSTGRES_USER=airflow \
  --from-literal=POSTGRES_PASSWORD="$DB_PW"

# 2) Airflow가 그 DB에 접속할 때 쓸 주소 (같은 비밀번호가 들어간다)
kubectl -n edu-airflow create secret generic airflow-metadata \
  --from-literal=connection="postgresql://airflow:${DB_PW}@airflow-postgres:5432/airflow"

# 3) Airflow가 저장하는 비밀번호 등을 암호화할 키
kubectl -n edu-airflow create secret generic airflow-fernet-key \
  --from-literal=fernet-key="$(head -c 32 /dev/urandom | base64 | tr '+/' '-_')"

# 4) 웹 화면의 로그인 세션을 보호할 키
kubectl -n edu-airflow create secret generic airflow-webserver-secret \
  --from-literal=webserver-secret-key="$(openssl rand -hex 16)"

unset DB_PW
kubectl -n edu-airflow get secret
```

```
NAME                       TYPE     DATA   AGE
airflow-db                 Opaque   3      0s
airflow-fernet-key         Opaque   1      0s
airflow-metadata           Opaque   1      0s
airflow-webserver-secret   Opaque   1      0s
```

`airflow-metadata`의 접속 주소에 있는 `airflow-postgres`는 Service 이름입니다(기초 과정 [03장](../../docs/03-service.md)). 같은 네임스페이스라서 이름만 적었습니다.

## 4. 실습 ② — Argo CD로 Airflow 설치

[02장](02-argocd.md)처럼 내 fork를 쓴다면 `repoURL`을 바꿔서 적용합니다(두 군데가 한 번에 바뀝니다).

```text
sed "s#kyeongseooh/k8s_edu#$GH_USER/k8s_edu#" platform/examples/argocd/app-airflow.yaml | kubectl apply -f -
```

fork 없이 원본 저장소를 그대로 쓰려면 이렇게 합니다. (6절의 Git 수정 실습만 할 수 없습니다)

```bash
kubectl apply -f platform/examples/argocd/app-airflow.yaml
```

설치가 진행되는 모습을 봅니다.

```bash
sleep 60
kubectl -n argocd get application edu-airflow
kubectl -n edu-airflow get pod,pvc
```

```
NAME          SYNC STATUS   HEALTH STATUS
edu-airflow   Synced        Progressing

NAME                                       READY   STATUS      RESTARTS      AGE
pod/airflow-create-user-9gjdk              1/1     Running     1 (24s ago)   27s
pod/airflow-postgres-0                     1/1     Running     0             55s
pod/airflow-run-airflow-migrations-k6rfj   0/1     Completed   0             27s
pod/airflow-scheduler-7d6c95874d-rrh2w     2/3     Running     0             27s
pod/airflow-statsd-5db88f8465-qpnsh        1/1     Running     0             27s
pod/airflow-webserver-647f9dc499-q8fvs     0/1     Running     0             27s

NAME                                            STATUS   VOLUME        CAPACITY   ACCESS MODES   STORAGECLASS   AGE
persistentvolumeclaim/airflow-logs              Bound    pvc-06c7...   1Gi        RWX            nfs-client     27s
persistentvolumeclaim/data-airflow-postgres-0   Bound    pvc-81ea...   2Gi        RWO            nfs-client     55s
```

`AGE`를 보면 **PostgreSQL이 먼저**(55초) 만들어지고 나머지가 그 뒤(27초)에 만들어졌습니다. `postgres.yaml`의 `argocd.argoproj.io/sync-wave: "-1"` 표시가 "이것부터 만들라"는 뜻입니다.

| Pod | 역할 |
|---|---|
| `airflow-postgres-0` | 데이터베이스 (StatefulSet) |
| `airflow-run-airflow-migrations-…` | DB에 테이블을 만드는 일회성 작업 (Job) → `Completed`가 정상 |
| `airflow-create-user-…` | 관리자 계정을 만드는 일회성 작업 (Job) |
| `airflow-scheduler-…` | 스케줄러. 컨테이너 3개(`scheduler`, `git-sync`, 로그 정리) |
| `airflow-webserver-…` | 화면 |
| `airflow-statsd-…` | 지표 변환기 ([06장](06-monitoring.md)) |

모두 준비될 때까지 기다립니다.

```bash
kubectl -n edu-airflow rollout status deployment/airflow-webserver --timeout=300s
kubectl -n argocd get application edu-airflow
kubectl -n edu-airflow get ingress
```

```
deployment "airflow-webserver" successfully rolled out

NAME          SYNC STATUS   HEALTH STATUS
edu-airflow   Synced        Healthy

NAME              CLASS   HOSTS                           ADDRESS      PORTS   AGE
airflow-ingress   nginx   edu-airflow.10.0.1.230.nip.io   10.0.1.230   80      2m
```

Argo CD 화면에서 `edu-airflow`를 열면, 우리가 직접 쓴 적 없는 리소스 20여 개가 트리로 보입니다. Helm 차트가 만들어 낸 것들입니다.

![Argo CD의 Airflow](../../images/platform/03-argocd-airflow.png)

## 5. 실습 ③ — Airflow 접속

상태 확인용 주소를 호출해 봅니다.

```bash
curl -s http://edu-airflow.10.0.1.230.nip.io/health
```

```
{"dag_processor": {...}, "metadatabase": {"status": "healthy"}, "scheduler": {"latest_scheduler_heartbeat": "2026-11-20T11:50:25.710148+00:00", "status": "healthy"}, "triggerer": {...}}
```

`metadatabase`(DB 연결)와 `scheduler`가 `healthy`이면 정상입니다.

브라우저에서 `http://edu-airflow.10.0.1.230.nip.io`에 접속합니다. 계정은 차트의 기본값인 `admin` / `admin`입니다.

![Airflow 로그인](../../images/platform/03-airflow-login.png)

![Airflow 첫 화면](../../images/platform/03-airflow-home.png)

DAG가 이미 보입니다. `values.yaml`의 `dags.gitSync` 설정에 따라, Scheduler 옆의 `git-sync` 컨테이너가 Git 저장소의 `platform/dags` 디렉터리를 받아 왔기 때문입니다. DAG는 [04장](04-airflow-dag.md)에서 실행합니다.

```bash
kubectl -n edu-airflow logs deploy/airflow-scheduler -c git-sync --tail=3
kubectl -n edu-airflow exec deploy/airflow-scheduler -c scheduler -- airflow dags list
```

```
dag_id        | fileloc                                               | owners  | is_paused
==============+=======================================================+=========+==========
harbor_report | /opt/airflow/dags/repo/platform/dags/harbor_report.py | airflow | True
hello_k8s     | /opt/airflow/dags/repo/platform/dags/hello_k8s.py     | airflow | True
```

> 실습용이라 기본 비밀번호를 그대로 썼습니다. 실제 환경에서는 반드시 바꿉니다. 화면 오른쪽 위의 사용자 메뉴 → **Your Profile** → **Reset my password**에서 바꿀 수 있습니다.

## 6. 실습 ④ — Git을 고쳐서 Airflow 바꾸기

화면 맨 위, 브라우저 탭 제목에 `EDU Airflow`라고 나옵니다. `values.yaml`의 이 부분에서 온 것입니다.

```yaml
config:
  webserver:
    instance_name: "EDU Airflow"
```

내 fork에서 `platform/gitops/airflow/values.yaml`을 열어 이 값을 `"HONG Airflow"`처럼 자기 이름으로 고치고 commit합니다([02장 5-2](02-argocd.md)와 같은 방법).

```bash
kubectl -n argocd annotate application edu-airflow argocd.argoproj.io/refresh=normal --overwrite
sleep 30
kubectl -n argocd get application edu-airflow
kubectl -n edu-airflow get pod | grep -E 'webserver|scheduler'
```

```
NAME          SYNC STATUS   HEALTH STATUS
edu-airflow   Synced        Progressing

airflow-scheduler-7d6c95874d-rrh2w     3/3     Running     0          12m
airflow-scheduler-b8bf8cbff-pd87k      2/3     Running     0          19s
airflow-webserver-647f9dc499-q8fvs     1/1     Running     0          12m
airflow-webserver-6c554f948b-ch5p6     0/1     Running     0          19s
```

설정이 바뀌었기 때문에 Scheduler와 Webserver가 **롤링 업데이트**로 교체되고 있습니다(옛 Pod와 새 Pod가 함께 보입니다). 끝나면 화면 제목이 바뀝니다.

```bash
kubectl -n edu-airflow rollout status deployment/airflow-webserver --timeout=300s
curl -s -L http://edu-airflow.10.0.1.230.nip.io/login/ | grep '<title>'
```

```
    <title>Sign In - EDU Airflow
```

같은 방법으로 Airflow 버전을 올리거나, 자원 크기를 바꾸거나, Executor를 바꿀 수 있습니다. **모든 변경이 Git 이력으로 남습니다.**

## 7. 고장 내고 고쳐 보기 — Secret을 빠뜨리면

실제로 고장을 내는 대신, 3절의 Secret을 만들지 않고 4절을 실행했다면 어떻게 됐을지 생각해 봅니다. 가장 흔한 실수입니다.

```text
NAME                                   READY   STATUS                       RESTARTS   AGE
airflow-postgres-0                     0/1     CreateContainerConfigError   0          40s
airflow-run-airflow-migrations-x7k2p   0/1     CreateContainerConfigError   0          12s
airflow-scheduler-7d6c95874d-9xkqp     0/3     Init:CreateContainerConfigError   0     12s
```

<details><summary>어떻게 원인을 찾고 고칠까요?</summary>

기초 과정 [05장](../../docs/05-secret.md)에서 본 상태입니다. `kubectl -n edu-airflow describe pod airflow-postgres-0`의 Events에 `secret "airflow-db" not found`가 나옵니다.

Argo CD 화면에서는 `Synced`이지만 `Progressing`/`Degraded`로 보입니다. Argo CD는 Git대로 반영했고, 그 결과가 정상이 아닌 것입니다([02장 6절](02-argocd.md)).

해결: Secret을 만들면 됩니다. Pod는 계속 재시도하고 있으므로 Secret이 생기면 스스로 시작합니다.

**Helm 차트가 요구하는 Secret의 이름과 key는 정해져 있습니다.** `values.yaml`에 적은 이름(`airflow-metadata` 등)과 실제 Secret 이름, 그리고 key 이름(`connection`, `fernet-key`, `webserver-secret-key`)이 정확히 같아야 합니다.

</details>

### Airflow가 뜨지 않을 때 확인 순서

| 증상 | 확인할 것 |
|---|---|
| Application이 `OutOfSync`/`Unknown`에서 멈춤 | `kubectl -n argocd get application edu-airflow -o jsonpath='{.status.conditions}'` — `repoURL`, `path`, values 파일 경로 |
| Pod가 `CreateContainerConfigError` | Secret 이름과 key |
| `airflow-postgres-0`이 `Pending` | PVC 상태 (`kubectl -n edu-airflow get pvc`) — 기초 과정 [06장](../../docs/06-pv-pvc.md) |
| `run-airflow-migrations`가 `Error` 반복 | DB 접속 문자열. `kubectl -n edu-airflow logs job/airflow-run-airflow-migrations` |
| Pod는 정상인데 화면이 `503` | Webserver가 아직 준비 중. `READY 1/1`이 될 때까지 대기 — 기초 과정 [16장](../../docs/16-probes.md) |
| 화면이 `404` | Ingress의 호스트 이름 — 기초 과정 [10장](../../docs/10-ingress.md) |

## 8. 정리

**이 Airflow는 [04장](04-airflow-dag.md)과 [06장](06-monitoring.md)에서 계속 씁니다. 지우지 않습니다.**

과정을 모두 마친 뒤에 지울 때는 이렇게 합니다.

```text
kubectl -n argocd delete application edu-airflow        # Airflow와 PostgreSQL이 함께 지워진다
kubectl -n edu-airflow delete pvc --all                 # StatefulSet의 PVC는 따로 지운다
kubectl delete namespace edu-airflow                    # Secret 포함 나머지

# 회수 정책이 Retain이라 남은 PV 정리 (기초 과정 06장 7절)
for pv in $(kubectl get pv -o jsonpath='{range .items[?(@.spec.claimRef.namespace=="edu-airflow")]}{.metadata.name}{"\n"}{end}'); do
  kubectl patch pv $pv -p '{"spec":{"persistentVolumeReclaimPolicy":"Delete"}}'
done
```

## 핵심 요약

- Airflow는 여러 작업을 순서대로, 정해진 시간에 실행하는 도구다. Scheduler, Webserver, DB로 이루어진다.
- KubernetesExecutor는 작업 하나마다 Pod를 하나 띄우고 끝나면 지운다.
- Helm 차트는 "설정값만 넣으면 완성되는 YAML 묶음"이다. 우리는 `values.yaml`만 관리한다.
- Argo CD Application은 출처를 여러 개 가질 수 있다(차트 + Git의 설정 파일 + Git의 YAML).
- 비밀 값은 Git에 넣지 않고 Secret으로 미리 만든다.
- `values.yaml`을 Git에서 고치면 Argo CD가 Airflow를 그에 맞게 바꾼다.

## 확인 문제

1. KubernetesExecutor와 CeleryExecutor의 차이는 무엇인가요?
2. 이 실습에서 Airflow를 만드는 재료 세 가지는 각각 어디에서 왔나요?
3. DB 비밀번호를 `values.yaml`에 적지 않고 Secret으로 따로 만든 이유는 무엇인가요?
4. `airflow-run-airflow-migrations` Pod의 상태가 `Completed`입니다. 문제가 있는 건가요?
5. `values.yaml`을 Git에서 고쳤더니 Scheduler와 Webserver Pod가 새로 만들어졌습니다. 서비스는 끊겼을까요?

<details><summary>정답 보기</summary>

1. CeleryExecutor는 항상 떠 있는 worker Pod에서 작업을 실행하고, KubernetesExecutor는 작업마다 새 Pod를 띄워 실행한 뒤 지웁니다.
2. Helm 차트는 Airflow 공식 차트 저장소에서, `values.yaml`과 `postgres.yaml`은 내 Git 저장소에서 왔습니다. 비밀 값은 `kubectl`로 직접 만든 Secret입니다.
3. Git에 올린 내용은 이력에 영원히 남고 저장소를 볼 수 있는 모든 사람에게 보입니다. 비밀 값은 Git 밖에서 관리합니다.
4. 아닙니다. DB 테이블을 만드는 일회성 Job이므로 `Completed`가 정상입니다.
5. 롤링 업데이트로 교체되므로 새 Pod가 준비된 뒤에 옛 Pod가 내려갑니다. 화면은 계속 접속됩니다.
</details>

---

다음 장: [04. Airflow DAG — 작업을 Pod로 실행하기](04-airflow-dag.md)
