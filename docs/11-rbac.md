# 11. RBAC — 누가 무엇을 할 수 있는가

> 여기서부터 14장까지는 **운영/관리자 영역**입니다. 개발자로서 쿠버네티스를 쓰기만 한다면
> "이런 구조로 권한이 걸려 있구나"를 이해하는 것이 목표입니다.

## 1. 개념

클러스터를 여러 사람/팀이 쓰면 권한 제어가 필요합니다. "인턴이 운영 DB의 Secret을 조회하면 안 되고,
CI 봇은 배포만 할 수 있어야 한다" 같은 것 말이죠.

**RBAC(Role-Based Access Control, 역할 기반 접근 제어)** 은 쿠버네티스의 권한 체계입니다.
구성 요소는 4가지인데, 2×2로 보면 쉽습니다.

| | 네임스페이스 범위 | 클러스터 전체 범위 |
|---|---|---|
| **권한 정의** ("무엇을 할 수 있나") | Role | ClusterRole |
| **권한 연결** ("누구에게 주나") | RoleBinding | ClusterRoleBinding |

- **Role**: 특정 네임스페이스 안에서의 권한 정의. 예: "default 네임스페이스에서 Pod를 읽고 생성 가능"
- **ClusterRole**: 클러스터 전체 수준의 권한 정의. 예: "모든 네임스페이스에서 Deployment 수정 가능"
- **RoleBinding**: 사용자/그룹/서비스어카운트를 Role(또는 ClusterRole)과 **특정 네임스페이스 안에서** 연결
- **ClusterRoleBinding**: ClusterRole을 **클러스터 전체 범위로** 연결

권한의 내용은 세 가지 축으로 정의합니다: **리소스**(pods, deployments...) × **동사(verb)**(get, list,
create, delete...) × **범위**(네임스페이스/클러스터).

> **비유**: Role/ClusterRole은 "직무기술서"(할 수 있는 일 목록), Binding은 "임명장"(이 사람에게
> 이 직무를 부여)입니다. 직무기술서만 있고 임명하지 않으면 아무 효력이 없습니다.

### ServiceAccount — 프로그램을 위한 계정

사람이 아닌 **프로그램(Pod, CI 파이프라인)** 이 쿠버네티스 API를 호출할 때 쓰는 계정이
**ServiceAccount(서비스어카운트, sa)** 입니다. "배포 봇 계정" 같은 것이죠.

## 2. 실습 — CI 봇에게 배포 권한만 주기

시나리오 (CKA 시험에도 나오는 전형적인 문제입니다):

> `deployment-clusterrole`이라는 ClusterRole을 만들어 **Deployment, StatefulSet, DaemonSet의
> 생성(create)만** 허용하라. `app-team1` 네임스페이스에 `cicd-token`이라는 ServiceAccount를 만들고,
> 이 권한을 **app-team1 네임스페이스로 한정해서** 부여하라.

```bash
# 0) 실습용 네임스페이스
kubectl create namespace app-team1

# 1) ClusterRole: 세 리소스에 대해 create 동사만 허용
kubectl create clusterrole deployment-clusterrole \
  --resource=deploy,sts,ds --verb=create

# 2) ServiceAccount 생성
kubectl create sa cicd-token -n app-team1

# 3) 연결: "app-team1 네임스페이스 안에서만" 적용하려면 RoleBinding을 사용
kubectl create rolebinding deployment-rolebinding \
  --clusterrole=deployment-clusterrole \
  --serviceaccount=app-team1:cicd-token -n app-team1
```

> **포인트**: ClusterRole(권한 정의는 클러스터 수준으로 재사용 가능하게)을 **RoleBinding**으로 묶으면
> "그 네임스페이스 안에서만" 유효해집니다. ClusterRoleBinding으로 묶으면 모든 네임스페이스에서
> 유효해지니 주의하세요.

### 권한이 제대로 걸렸는지 확인 — `kubectl auth can-i`

`--as` 옵션으로 "그 계정인 척"하고 물어볼 수 있습니다.

```bash
kubectl auth can-i create sts -n app-team1 \
  --as=system:serviceaccount:app-team1:cicd-token
# yes     ← create는 허용했으니

kubectl auth can-i delete sts -n app-team1 \
  --as=system:serviceaccount:app-team1:cicd-token
# no      ← delete는 안 줬으니

kubectl auth can-i create deploy -n default \
  --as=system:serviceaccount:app-team1:cicd-token
# no      ← 다른 네임스페이스라서
```

## 3. YAML로 보는 실전 패턴 2가지

명령어 대신 YAML로 쓰면 이렇게 됩니다. (예: SSO 그룹 `dev`에게 권한 부여)

### 패턴 ① 클러스터 전체 admin 권한

([examples/11-rbac/clusterrole-admin.yaml](../examples/11-rbac/clusterrole-admin.yaml))

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: keycloak-admin
rules:
- apiGroups: ["*"]      # 모든 API 그룹의
  resources: ["*"]      # 모든 리소스에
  verbs: ["*"]          # 모든 동작을 허용
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding        # ← 클러스터 전체 범위로 연결
metadata:
  name: keycloak-admin-binding
subjects:
- kind: Group                   # 사용자 그룹에게 (User, ServiceAccount도 가능)
  name: dev
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: keycloak-admin
  apiGroup: rbac.authorization.k8s.io
```

### 패턴 ② 같은 권한을 default 네임스페이스에만

([examples/11-rbac/clusterrole-ns-admin.yaml](../examples/11-rbac/clusterrole-ns-admin.yaml))

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole               # 권한 정의는 재사용 가능하게 ClusterRole로
metadata:
  name: keycloak-default-admin
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding               # ← 바인딩을 RoleBinding으로 하면 해당 ns로 한정됨
metadata:
  name: default-role-binding
  namespace: default            # 이 네임스페이스 안에서만 유효
subjects:
- kind: Group
  name: dev
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: keycloak-default-admin
  apiGroup: rbac.authorization.k8s.io
```

두 패턴의 차이는 **Binding의 종류**뿐입니다. 권한의 "범위"는 Role/ClusterRole이 아니라
**어떤 Binding으로 묶느냐**가 최종 결정한다는 것이 RBAC의 핵심 감각입니다.

## 4. 실습 정리

```bash
kubectl delete rolebinding deployment-rolebinding -n app-team1
kubectl delete clusterrole deployment-clusterrole
kubectl delete sa cicd-token -n app-team1
kubectl delete namespace app-team1
```

## 확인 문제

1. Role과 ClusterRole의 차이는?
2. ClusterRole을 RoleBinding으로 바인딩하면 권한의 유효 범위는?
3. 어떤 계정이 특정 작업을 할 수 있는지 미리 확인하는 명령은?

<details><summary>정답 보기</summary>

1. Role은 특정 네임스페이스 안의 권한 정의, ClusterRole은 클러스터 전체 수준의 권한 정의
2. RoleBinding이 속한 **그 네임스페이스 안으로 한정**된다 (ClusterRole의 재사용 패턴)
3. `kubectl auth can-i <동사> <리소스> -n <ns> --as=<계정>`
</details>

---

다음 장: [12. NetworkPolicy — Pod 사이의 방화벽](12-networkpolicy.md)
