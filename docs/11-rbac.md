# 11. RBAC — 누가 무엇을 할 수 있는가

> 여기서부터 14장까지는 **운영/관리자 영역**입니다. 개발자로서 쿠버네티스를 쓰기만 한다면
> "이런 구조로 권한이 걸려 있구나"를 이해하는 것이 목표입니다.
>
> 이 장부터는 **사고 대응 실습** 형식으로 진행합니다. 정상 상태를 만든 뒤 → 실제로
> 문제를 일으키고 → 증거를 보며 원인을 추론하고 → (막히면 펼쳐보는) 복구 절차로 고치고 →
> 성공 기준으로 확인하고 → 정리합니다. 리소스 이름은 장마다 겹치지 않게 만들어서, 0장에서
> 배정받은 **개인 네임스페이스(`$NS`)** 를 그대로 계속 써도 다른 장과 충돌하지 않습니다.
> 이 장에서는 네임스페이스를 새로 만들거나 지우지 않습니다.

## 1. 개념

클러스터를 여러 사람/팀이 쓰면 권한 제어가 필요합니다. "인턴이 운영 DB의 Secret을 조회하면 안 되고,
CI 봇은 배포만 할 수 있어야 한다" 같은 것 말이죠.

**RBAC(Role-Based Access Control, 역할 기반 접근 제어)** 은 쿠버네티스의 권한 체계입니다.
구성 요소는 4가지인데, 2×2로 보면 쉽습니다.

| | 네임스페이스 범위 | 클러스터 전체 범위 |
|---|---|---|
| **권한 정의** ("무엇을 할 수 있나") | Role | ClusterRole |
| **권한 연결** ("누구에게 주나") | RoleBinding | ClusterRoleBinding |

- **Role**: 특정 네임스페이스 안에서의 권한 정의. 예: "내 네임스페이스에서 Pod를 읽을 수 있음"
- **RoleBinding**: 사용자/그룹/서비스어카운트를 Role(또는 ClusterRole)과 **특정 네임스페이스 안에서** 연결
- **ClusterRole / ClusterRoleBinding**: 같은 개념을 클러스터 전체 범위로 확장한 것 (노드처럼
  네임스페이스가 없는 리소스를 다루거나, 여러 네임스페이스에 같은 권한을 재사용할 때 씀)

권한의 내용은 세 가지 축으로 정의합니다: **리소스**(pods, configmaps...) × **동사(verb)**(get, list,
create, delete...) × **범위**(네임스페이스/클러스터).

> **비유**: 사무실 출입카드 시스템과 똑같습니다. Role은 "어떤 문을 열 수 있는 카드인가"(직무기술서),
> RoleBinding은 "이 카드를 누구에게 발급하는가"(임명장)입니다. 카드 종류만 만들어 놓고 아무에게도
> 발급하지 않으면 아무 효력이 없습니다.

### ServiceAccount — 프로그램을 위한 계정

사람이 아닌 **프로그램(Pod, CI 파이프라인)** 이 쿠버네티스 API를 호출할 때 쓰는 계정이
**ServiceAccount(서비스어카운트, sa)** 입니다. "로봇 직원 사원증" 같은 것이죠.

> **최소 권한(least privilege) 원칙**: 이 장에서는 흔히 보이는 "일단 전체 권한(`*`/`*`/`*`)을
> 주고 보자" 패턴을 다루지 않습니다. 실무에서 `apiGroups: ["*"], resources: ["*"], verbs: ["*"]`
> ClusterRole을 함부로 묶으면, 그 권한을 받은 주체가 **다른 사람의 RBAC 권한까지 마음대로
> 바꿀 수 있는** 사실상의 클러스터 관리자가 됩니다. 실무에서는 "이 SA가 정확히 무엇을 해야
> 하는가"부터 적고, 거기에 필요한 최소한의 리소스·동사만 허용합니다.

## 2. 정상 상태 만들기 — 최소 권한 SA

시나리오: `viewer-bot`이라는 ServiceAccount에게 "내 네임스페이스의 Pod 조회"만 허용합니다.
([examples/11-rbac/sa-role.yaml](../examples/11-rbac/sa-role.yaml))

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: viewer-bot
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
```

RoleBinding은 **처음부터 올바른 버전**을 적용합니다.
([examples/11-rbac/rolebinding-fixed.yaml](../examples/11-rbac/rolebinding-fixed.yaml))

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: viewer-bot-pod-reader
subjects:
- kind: ServiceAccount
  name: viewer-bot
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

```bash
k apply -f examples/11-rbac/sa-role.yaml
k apply -f examples/11-rbac/rolebinding-fixed.yaml
```

`kubectl auth can-i`로 "그 계정인 척" 물어서 **허용(allow)/거부(deny)** 를 확인합니다.

> **impersonation 전제 조건**: `--as`를 쓰려면 **지금 로그인된 내 계정**이 `impersonate` 권한
> (정확히는 `users`/`groups`/`serviceaccounts` 리소스에 대한 `impersonate` verb)을 가지고
> 있어야 합니다. 실습용 관리자 kubeconfig(cluster-admin)에는 보통 기본 포함되어 있습니다.

```bash
k auth can-i get pods --as="system:serviceaccount:${NS}:viewer-bot"
# yes  ← Role에 넣어준 권한

rc=0
k auth can-i delete pods --as="system:serviceaccount:${NS}:viewer-bot" || rc=$?
echo "exit=$rc"
# no, exit=1  ← verbs에 delete를 안 넣었으니 거부 (의도된 거부, 정상)
```

여기까지가 **정상 상태**입니다: `get pods`는 허용(exit 0), `delete pods`는 거부(exit 1)입니다.

## 3. 장애 발생 — "읽기 권한을 줬는데 안 된대요"

운영팀이 Role 이름을 리네이밍하는 작업을 하다가, RoleBinding은 옛 이름을 가리키는 버전으로
**재배포(재생성)** 해버린 상황을 재현합니다 (흔한 실수: Role은 바뀌었는데 바인딩이 안 따라감).
([examples/11-rbac/rolebinding-broken.yaml](../examples/11-rbac/rolebinding-broken.yaml))

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: viewer-bot-pod-reader
subjects:
- kind: ServiceAccount
  name: viewer-bot
roleRef:
  kind: Role
  name: pod-reader-old     # ★ 존재하지 않는 Role 이름 (오타)
  apiGroup: rbac.authorization.k8s.io
```

```bash
k delete rolebinding viewer-bot-pod-reader
k apply -f examples/11-rbac/rolebinding-broken.yaml

rc=0
k auth can-i get pods --as="system:serviceaccount:${NS}:viewer-bot" || rc=$?
echo "exit=$rc"
# no, exit=1   ← 장애 재현: 의도한 건 yes인데 거부로 바뀜
```

### 증거 / 질문

```bash
k get rolebinding viewer-bot-pod-reader -oyaml | grep -A3 roleRef
# roleRef: {kind: Role, name: pod-reader-old, apiGroup: rbac.authorization.k8s.io}

k get role pod-reader -oyaml | grep -A3 resources
# resources: ["pods"]   ← Role 자체는 멀쩡함
```

- RoleBinding이 가리키는 Role 이름과, 실제로 존재하는 Role 이름을 비교해 보세요.
- SA/Role은 정상인데, 왜 `get pods`가 "no"로 나올까요?
- 이 상황에서 `kubectl edit rolebinding ...`으로 `roleRef.name`만 고치면 될까요?
  (`roleRef`는 생성 후 **불변(immutable)** 필드입니다 — 직접 해보고 에러 메시지를 확인해도 좋습니다.)

## 4. 복구 (막혔을 때만 펼쳐보세요)

<details><summary>복구 절차 보기</summary>

`roleRef`는 불변 필드라 patch/edit으로 고칠 수 없습니다. 바인딩을 **지우고 다시 만들어야** 합니다.
([examples/11-rbac/rolebinding-fixed.yaml](../examples/11-rbac/rolebinding-fixed.yaml))

```bash
k delete rolebinding viewer-bot-pod-reader
k apply -f examples/11-rbac/rolebinding-fixed.yaml

k get rolebinding viewer-bot-pod-reader -oyaml | grep -A3 roleRef
# roleRef: {kind: Role, name: pod-reader, apiGroup: rbac.authorization.k8s.io}
```

</details>

## 5. 성공 판정

```bash
k auth can-i get pods --as="system:serviceaccount:${NS}:viewer-bot"
# yes  ← 고쳐졌다

rc=0
k auth can-i delete pods --as="system:serviceaccount:${NS}:viewer-bot" || rc=$?
echo "exit=$rc"
# no, exit=1   ← 필요한 것만 됐지, 전체 권한이 풀린 게 아님을 재확인
```

두 가지가 모두 맞으면 성공입니다: ① 의도했던 `get pods`가 허용으로 바뀜, ② `delete pods`처럼
주지 않은 권한은 여전히 거부.

## 6. 정리

```bash
k delete rolebinding viewer-bot-pod-reader
k delete role pod-reader
k delete serviceaccount viewer-bot
```

## 확인 문제

1. Role과 ClusterRole의 차이는?
2. `kubectl auth can-i ... --as=...`를 쓸 때 반드시 필요한 전제 조건은?
3. 이번 장애의 근본 원인은 무엇이었고, `roleRef`를 고치려면 왜 patch/edit이 아니라
   삭제 후 재생성이 필요한가?

<details><summary>정답 보기</summary>

1. Role은 특정 네임스페이스 안의 권한 정의, ClusterRole은 클러스터 전체 수준(또는 재사용 가능한)
   권한 정의
2. 내 계정이 `users`/`groups`/`serviceaccounts`에 대한 `impersonate` 권한을 갖고 있어야 한다.
3. RoleBinding의 `roleRef`가 존재하지 않는 Role 이름을 가리키고 있었다(오타). `roleRef`는
   생성 후 불변 필드로 설계되어 있어서(바인딩 대상이 수시로 바뀌는 걸 막기 위한 안전장치),
   고치려면 바인딩 자체를 삭제하고 올바른 `roleRef`로 다시 만들어야 한다.
</details>

---

다음 장: [12. NetworkPolicy — Pod 사이의 방화벽](12-networkpolicy.md)
