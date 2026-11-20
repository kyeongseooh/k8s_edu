# 03. “팀 예산을 바꿔 주세요” — 정책도 Git으로 배포하기

**Namespace**는 자원의 소속, **ResourceQuota**는 그 공간 전체 예산, **LimitRange**는 개별 컨테이너의 기본값·허용 범위다. quota를 늘린다고 노드 CPU가 늘지는 않는다. 스케줄러의 `Insufficient cpu`와 API가 생성 전 거부하는 `exceeded quota`는 서로 다른 문제다.

## 실습 1. Git 변경 한 건을 끝까지 추적

예제 저장소 이력에는 `pods: 8 → 10`, 기본 CPU 요청 `25m → 50m`로 바꾼 별도 정책 커밋이 있다. **현재 `main`은 변경 후 값**이다. 재실습은 개인 앱이 추적하는 브랜치에서 `10 → 11`, `50m → 60m`처럼 승인 가능한 작은 변경으로 반복한다. 운영 정책은 건드리지 않는다.

```bash
# GitOps 저장소 및 개인 교육 환경
k get quota team-budget; k describe limitrange container-defaults
k run budget-before --image=nginx:1.27-alpine --restart=Never --command -- sleep 900
k get pod budget-before -o jsonpath='{.spec.containers[0].resources}{"\n"}'
git switch -c lesson/change-budget
# clusters/training/policy.yaml의 spec.hard.pods와 defaultRequest.cpu만 변경한다.
git diff -- clusters/training/policy.yaml
kubectl kustomize clusters/training > /dev/null
git add clusters/training/policy.yaml
git commit -m '교육 전용 Pod 예산과 기본 요청 조정'
git push -u origin lesson/change-budget
```

GitHub에서 PR을 리뷰하고 **해당 교육 Application이 추적하는 브랜치**에 머지한다. feature 브랜치에만 push하면 `main`을 추적하는 앱에는 아무 일도 일어나지 않는다. Argo CD UI의 App → History and Rollback 또는 아래 명령에서 **머지 후 실제 SHA**를 대조한다. 자동 감지까지 기다리거나 Refresh를 사용한다.

```bash
git ls-remote origin refs/heads/main
kc -n argocd get application edu-platform-lab -o jsonpath='{.status.sync.revision}{" "}{.status.sync.status}{"\n"}'
k get quota team-budget -o jsonpath='{.status.hard.pods}{"\n"}'
k get limitrange container-defaults -o jsonpath='{.spec.limits[0].defaultRequest.cpu}{"\n"}'
k run budget-after --image=nginx:1.27-alpine --restart=Never --command -- sleep 900
for p in budget-before budget-after; do k get pod "$p" -o jsonpath='{.metadata.name}{": "}{.spec.containers[0].resources.requests.cpu}{"\n"}'; done
```

**성공 기준:** Git SHA와 Argo revision이 일치하고, 두 Pod에 서로 다른 CPU 요청이 남아 있다. LimitRange는 admission 시 빈 값을 채우므로 **기존 Pod의 값을 소급 수정하지 않는다.**

## 실습 2. 노드를 과부하시키지 않고 quota 거부 재현

아래는 각각 `1200m`를 요청하는 두 컨테이너다. 각각은 컨테이너당 최대 2 CPU 이하지만 합계 2.4 CPU는 **namespace 총 requests.cpu=2**를 단독으로도 초과한다. 서버 dry-run으로 admission 결과만 본다.

```bash
k create --dry-run=server -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata: {name: budget-over}
spec:
  containers:
  - name: a
    image: nginx:1.27-alpine
    resources: {requests: {cpu: 1200m}, limits: {cpu: 1200m}}
  - name: b
    image: nginx:1.27-alpine
    resources: {requests: {cpu: 1200m}, limits: {cpu: 1200m}}
YAML
```

기대 결과는 `Forbidden ... exceeded quota`와 `requested / used / limited` 값이다. Pod는 생성되지 않으므로 Pod 로그가 없다. quota가 다른 환경이면 먼저 `k describe quota team-budget`의 실제 상한을 확인한다. Deployment였다면 Pod 생성에 실패한 ReplicaSet의 Events에 `FailedCreate`가 남는다.

<details><summary>복구와 정리</summary>

한도부터 높이지 않는다. 작업의 실측 요구량과 이미 예약한 양을 먼저 확인한다. `1200m`를 두 곳 모두 `20m`로 줄인 뒤 **같은 dry-run**을 다시 한다. 여유가 있는 환경에서 `created (server dry run)`이면 성공이다. 정책 자체가 잘못됐다면 해당 정책 커밋만 revert하는 PR을 올리고 **복구 커밋의 SHA**까지 확인한다. `k edit quota`만 하면 self-heal이 Git 값으로 되돌린다.

```bash
k delete pod budget-before budget-after --ignore-not-found
```
</details>
