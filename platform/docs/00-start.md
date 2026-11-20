# 00. 어느 계정으로, 어디에서 실행하는가?

이번 실습에는 ‘관리자’ 하나가 아니라 다음 네 가지 신원이 등장한다. 한 단계가 성공해도 다음 권한이 생기는 것은 아니다.

| 주체 | 허용할 일 | 허용하지 않을 일 |
|---|---|---|
| 이미지 제작자 | 교육 Harbor 프로젝트에 push | 클러스터 전체 관리 |
| Argo CD | 지정 Git 저장소 read, 승인된 리소스 동기화 | Git에 password 기록, 다른 팀 목적지 배포 |
| Airflow scheduler | 자기 namespace에 task Pod 생성·로그 읽기·정리 | 노드·다른 namespace·Secret 조회 |
| 작업 Pod | 이미지에 담긴 계산만 실행 | 사용자 토큰이나 scheduler 계정 재사용 |

실습에는 **별도 GitOps 저장소의 clone**, Bash/Git/Docker/kubectl, 플랫폼 관리자가 지정한 실습용 컨텍스트가 필요하다. `kubectl`의 기본 컨텍스트를 바꾸지 않고 아래 함수를 같은 셸에서 쓴다. 실제 서비스 URL·신뢰할 CA·계정은 플랫폼 관리자에게 별도로 받는다. 모든 `.invalid` 주소는 예시다.

```bash
export CTX="$(kubectl config current-context)" NS=edu-platform-lab
kc() { kubectl --context "${CTX:?}" "$@"; }
k()  { kc -n "${NS:?}" "$@"; }
printf '대상: %s / %s\n' "$CTX" "$NS"
kc cluster-info
```

운영 컨텍스트나 소유자가 다른 `edu-platform-lab`이면 중단한다. 해당 이름은 [02장](02-gitops.md)에서 **Git이 생성**하므로 미리 `kubectl create ns` 하지 않는다. UI와 클러스터 CLI는 서로 다른 자격 증명을 쓴다. HTTP로만 노출된 관리자 화면에 비밀번호를 전송하는 실습은 하지 않는다. 권한이 없는 단계는 플랫폼 관리자에게 요청한다.

### 현재 구성에서 혼동하기 쉬운 세 가지

- 기존 Argo Application `airflow`는 **chart 1.16.0**을 읽고, Airflow 2.10.4의 scheduler/worker는 **CeleryExecutor**와 **DAG git-sync**를 사용한다. GitOps는 인프라 선언을, git-sync는 DAG 파일을 가져온다. 이번 입문 실습은 비교를 위해 독립 scheduler와 작은 DAG ConfigMap을 쓴다.
- Kubeflow 웹에서 Keycloak 로그인이 되어도 kubectl이 Keycloak 토큰을 신뢰한다는 뜻은 아니다. 현재 API 서버에는 OIDC 설정이 없다. [05장](05-keycloak-kubectl.md)의 관리자 전제가 먼저다.
- 기존 Prometheus에는 Kubernetes 지표가 있다. 기존 Airflow의 StatsD는 꺼져 있으므로 `airflow`를 검색해서 데이터가 없다고 곧바로 장애로 신고하지 않는다.

**확인 과제:** 기존 Airflow 배포 선언의 소스와 상태를 변경 없이 확인한다(읽기 권한이 없다면 플랫폼 관리자에게 조회를 요청).

```bash
kc -n argocd get application airflow -o custom-columns='NAME:.metadata.name,CHART:.spec.source.chart,VERSION:.spec.source.targetRevision,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

`Synced`는 Git/chart 선언과의 일치, `Healthy`는 컨트롤러가 본 리소스의 건강 상태다. **DAG 실행 성공은 어느 쪽도 보장하지 않는다.**
