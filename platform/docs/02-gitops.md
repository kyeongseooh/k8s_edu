# 02. Git을 읽어서 Namespace와 Airflow를 만들기

**목표:** GitHub에 YAML을 올리는 것과 Argo CD가 실제로 배포하는 것을 구분한다. Argo는 `repoURL + targetRevision + path`가 가리키는 결과를 **destination** 클러스터에 맞춘다. 기존 `argocd/airflow`나 그 Helm release는 수정하지 않는다.

## 설정 저장소의 지도

```text
bootstrap/project.yaml       강사가 승인할 소스·목적지·리소스 종류
bootstrap/application.yaml   읽을 리비전(main)과 경로(clusters/training)
clusters/training/           Namespace, quota, LimitRange, RBAC, Airflow, 지표
  task-image.properties      DAG에 전달할 Harbor 이미지 digest (비밀 아님)
dags/report.py               KubernetesPodOperator DAG
images/task/                 실제 계산을 수행하는 이미지 소스
```

실습용 [private 원본](https://github.com/kyeongseooh/k8s-platform-gitops)이 이미 있다. 새 팀이라면 **새 빈 private Git 저장소**를 만들고 이 구조를 복사한다. `bootstrap/` 두 파일의 repoURL과 namespace를 자기 환경에 맞춰 함께 리뷰한다. 원본 저장소의 `main`을 개인 실습 결과로 덮어쓰지 않는다. Git에 인증값을 넣을 필요는 없다.

## 강사: 최초 한 번만 신뢰 관계 등록

1. **GitHub → Settings → Deploy keys:** 이 저장소에만 사용할 키 쌍의 *공개키*를 등록하고 **Allow write access는 끈다**. 개인 PAT를 Argo에 넣지 않는다. Argo CD 관리자는 승인된 `bootstrap/project.yaml`로 `edu-platform` AppProject를 먼저 등록한다. SSH 서버 키는 검증된 `known_hosts`를 사용한다.
2. **Argo CD → Settings → Repositories → Connect repo:** SSH를 선택하고 project `edu-platform`, Git URL은 `bootstrap/application.yaml`과 **문자 그대로 동일하게**, private key는 비밀 입력란에만 전달한다. `Successful`은 Git 읽기에 성공했다는 뜻이지 배포 완료가 아니다. 자격 증명은 Kubernetes Secret에 보관되므로 `argocd` namespace의 Secret 읽기 권한도 제한한다.
3. **Applications → New App → Edit as YAML:** `bootstrap/application.yaml`을 검토해 등록한다. 확인할 필드: 이름 `edu-platform-lab`, `spec.project: edu-platform`, `targetRevision: main`, `path: clusters/training`, destination의 namespace `edu-platform-lab`. **공유 `airflow` 앱을 선택하지 않는다.** 기존 대상 namespace가 다른 소유자라면 중단한다. 관리자가 허용하기 전에는 이 장을 렌더링까지만 진행한다.

Namespace는 cluster-scoped라 AppProject의 허용 목록에 `Namespace`가 필요하다. **종류 허용은 이름별 권한 통제가 아니다.** 팀에 bootstrap·project 수정 권한을 주지 말고 강사 소유 저장소/보호 브랜치·필수 리뷰를 사용한다. 신뢰되지 않은 팀이라면 Namespace·quota를 별도 관리자 앱/저장소로 분리하고 팀 앱에는 cluster-scoped 권한을 주지 않는 것이 낫다.

## 개발자: 반영 전에 결과를 먼저 읽기

```bash
# GitOps 저장소 루트
kubectl kustomize clusters/training | grep -E '^kind:|^  namespace:|^  name:'
git ls-remote origin refs/heads/main
```

Argo의 sync wave **-3**에서 Namespace, **-2**에서 quota·LimitRange가 먼저 생긴다. 이후 교육 scheduler·RBAC·StatsD가 만들어진다. `CreateNamespace=true`에만 기대지 않으므로 namespace 라벨과 정책도 검토 가능한 Git 이력이다. DAG와 작업 이미지 설정은 Kustomize가 내용 hash를 붙인 ConfigMap으로 만든다. 내용이 바뀌면 Deployment의 참조도 바뀐다.

```bash
# 00장의 kc/k 사용
kc -n argocd get application edu-platform-lab -o custom-columns='COMMIT:.status.sync.revision,SYNC:.status.sync.status,HEALTH:.status.health.status'
k get resourcequota,limitrange,deploy,svc
k rollout status deploy/edu-airflow --timeout=180s
```

**성공 판정:** `COMMIT`이 원격 `main`의 SHA와 같고 `Synced`, scheduler가 Ready이어야 한다. `OutOfSync`는 차이가 있다는 뜻이다. `ComparisonError`/`Unknown`이면 먼저 **App → Conditions**에서 repo 연결, path, Kustomize 오류를 본다. `Synced`지만 `Degraded`면 workload의 Events·로그를 확인한다. 실제 DAG 성공 여부는 [04장](04-airflow.md)에서 확인한다.

## 강사: Kubernetes에 pull 전용 자격 증명 지급

[01장](01-image-harbor.md)에서 reader 로그인한 Docker 설정만 사용한다. `config.json`의 `auths`에 해당 registry 항목이 있는지 **값을 출력하지 않고** 확인한다. OS credential helper를 가리키는 파일만 복사하면 노드에서 로그인할 수 없다. 동명의 Secret이 이미 있으면 덮어쓰지 말고 소유자를 확인한다.

```bash
k create secret generic edu-harbor-pull --type=kubernetes.io/dockerconfigjson \
  --from-file=.dockerconfigjson="${PULL_CONFIG:?}/config.json"
k get secret edu-harbor-pull -o jsonpath='{.type}{"\n"}'
docker --config "$PULL_CONFIG" logout "$HARBOR_HOST"
```

이 Secret은 Git 관리 대상이 아니다. 교육용 범위·만료를 정하고 교체 후 **새 Pod로 pull**을 확인한다. 운영에서는 승인된 외부 비밀 관리기를 사용한다.

## 장애 대응 과제 · 종료

**과제:** 개인 브랜치에서 `clusters/training/kustomization.yaml`에 잘못된 상대 경로를 넣고 `kubectl kustomize clusters/training`을 실행한다. 어느 파일을 못 찾는지 기록한다. 경로를 고쳐 성공하기 전에는 머지하지 않는다. 이미 배포된 잘못된 선언은 UI에서 live 객체만 고치지 말고 Git에서 revert한다.

**종료는 강사만:** Application과 실제 namespace의 소유 라벨·대상 클러스터를 다시 확인한다. 다음 수업에서 쓰지 않으면 먼저 교육 Application의 자동 동기화를 해제하고 **교육 Application만** 제거한다. 비연쇄 삭제 시 자식 리소스는 남는다. `edu-platform-lab`이 온전히 폐기 가능한 전용 공간임을 확인한 뒤 그 공간을 반납한다. 교육 deploy key·repo credential·만료 robot도 회수한다. 공용 `argocd`, `airflow`, 모니터링 namespace는 삭제하지 않는다.
