# 05. Keycloak 로그인과 kubectl 권한은 어디서 연결될까?

**Keycloak은 신원을 증명하고 Kubernetes RBAC는 행동을 허가한다.** Kubeflow 웹 로그인이 잘 돼도 kubectl 로그인과는 별개다. 이 교육 클러스터는 조회 시점에 kube-apiserver에 `--oidc-*`/별도 authentication config가 없었고 제공된 Keycloak UI도 HTTP였다. **따라서 아래는 선행 구성이 필요한 운영 가이드이지 이 클러스터에서 이미 성공한 OIDC 로그인 절차가 아니다.** 기존 Kubeflow client를 재사용하지 않는다.

## 1. IAM 관리자가 준비할 것

1. 교육 realm의 정식 **HTTPS issuer**를 정한다. API 서버와 사용자 PC에서 같은 이름·신뢰된 CA로 `<issuer>/.well-known/openid-configuration`을 읽고 JSON `issuer`와 설정 문자열이 정확히 일치해야 한다. `master` 관리 콘솔 URL이나 HTTP URL이 아니다.
2. **Keycloak → 해당 realm → Clients → Create OpenID Connect client**: 예시 ID `k8s-cli`; Client authentication **Off**(public), Standard flow **On**, Direct access grants **Off**, PKCE method **S256**. kubelogin이 쓸 callback `http://localhost:8000`을 정확히 등록하고 실제 배포 플러그인의 redirect URI와 일치시킨다. localhost loopback 예외가 원격 issuer의 HTTP를 허용하는 것은 아니다. wildcard redirect나 client secret 배포는 사용하지 않는다.
3. 전용 그룹 `edu-readers` 생성, 교육 사용자만 추가한다. **Client scopes → k8s-cli-dedicated → Mappers → Group Membership**: claim name `groups`, Add to ID token **On**. 아래 예제는 Full group path **Off**라 값이 `edu-readers`다. On이면 `/edu-readers`가 되므로 바인딩도 달라진다. 같은 leaf 이름을 가진 그룹이 여러 개라면 full path를 선택한다. 이미 검증한 이메일 대신 여기서는 고정 식별자인 `sub`를 사용자 이름으로 쓴다.

## 2. 클러스터 관리자 작업 — 공유 교육 환경에서는 적용하지 않음

API 서버가 신뢰할 예시 설정은 다음과 같다. **명령이 아니라 kubeadm static Pod command의 인자 예시**다. `--oidc-ca-file`은 API 서버 컨테이너 *안에서 읽을 수 있는* issuer CA 경로여야 한다(필요 시 read-only mount). 사용자 kubeconfig의 클러스터 CA와 다른 용도다.

```text
--oidc-issuer-url=https://sso.example.invalid/realms/training
--oidc-client-id=k8s-cli
--oidc-username-claim=sub
--oidc-username-prefix=oidc:
--oidc-groups-claim=groups
--oidc-groups-prefix=oidc:
--oidc-ca-file=/etc/kubernetes/oidc/issuer-ca.crt
```

운영 변경은 점검 창·콘솔 접근·기존 break-glass 인증을 확보한 뒤 한다. 원본과 CA/mount 설정 백업은 **static Pod 감시 디렉터리 밖**에 보관한다. HA면 한 대씩 적용하고 독립 관리자 인증으로 `/readyz`, API server 로그, 기존 인증과 신규 OIDC 인증을 각각 검증한다. 단일 control-plane이면 재시작 중 API 중단이 있을 수 있다. 실패하면 원래 manifest와 mount를 복원하고 `/readyz`를 재확인한다. kubeadm 업그레이드로 설정이 덮이지 않도록 관리 원본에도 반영한다.

## 3. RBAC: 읽기 권한만 주기

[Role + RoleBinding 예제](../examples/oidc/pod-reader.yaml)는 이름이 **`oidc:edu-readers`인 그룹**에 자기 namespace의 Pod `get/list/watch`만 부여한다. Keycloak 그룹이 동일해도 namespace별로 RoleBinding이 없으면 이 권한은 생기지 않는다. 관리자가 대상·소유권을 확인하고 개인 교육 namespace에서만 적용한다. 실습 프로젝트를 GitOps로 관리한다면 강사가 승인한 Git 경로에 예제를 추가한다.

```bash
# 관리자: 교재 루트에서, 강사가 직접 관리하는 개인 namespace인 경우만 적용한다.
# GitOps 관리 대상이라면 아래 apply 대신 승인된 Git 변경으로 반영한다.
kc -n "$NS" apply -f platform/examples/oidc/pod-reader.yaml
# impersonate 권한이 있는 기존 관리자 컨텍스트로 확인. OIDC 토큰은 사용하지 않는다.
kc auth can-i get pods -n "$NS" --as=oidc:sample-subject --as-group=oidc:edu-readers
kc auth can-i delete pods -n "$NS" --as=oidc:sample-subject --as-group=oidc:edu-readers
```

의도한 답은 `yes / no`다. 이는 **RBAC만 검증**한 것이다. 그 사용자가 다른 바인딩으로 추가 권한을 받았다면 합산되므로 함께 확인한다.

## 4. 교육생: 독립 kubeconfig로 실제 로그인

전제 충족 후 신뢰된 배포 경로에서 kubectl 플러그인 `oidc-login`(int128/kubelogin)을 설치한다. 강사에게 받은 서버 URL과 두 CA 경로를 사용한다. 아래 명령은 **새 파일만** 만들며 기존 관리자 kubeconfig에서 인증 데이터를 복사하지 않는다.

```bash
: "${API_SERVER:?}" "${CLUSTER_CA:?}" "${OIDC_ISSUER:?}" "${ISSUER_CA:?}" "${NS:?}"
OIDC_DIR=$(mktemp -d); OIDC_CFG="$OIDC_DIR/config"
ku() { kubectl --kubeconfig "$OIDC_CFG" "$@"; }
ku config set-cluster training --server="$API_SERVER" --certificate-authority="$CLUSTER_CA" --embed-certs=true
ku config set-credentials learner --exec-command=kubectl --exec-api-version=client.authentication.k8s.io/v1 --exec-interactive-mode=IfAvailable \
  --exec-arg=oidc-login --exec-arg=get-token --exec-arg="--oidc-issuer-url=$OIDC_ISSUER" --exec-arg=--oidc-client-id=k8s-cli \
  --exec-arg=--oidc-pkce-method=S256 --exec-arg=--listen-address=localhost:8000 --exec-arg="--certificate-authority=$ISSUER_CA"
ku config set-context learner --cluster=training --user=learner --namespace="$NS"
ku config use-context learner
ku auth whoami
ku auth can-i get pods -n "$NS"
ku auth can-i delete pods -n "$NS"
```

**성공 증거:** 실제 로그인 후 `auth whoami`에 `oidc:<sub>`와 `oidc:edu-readers`, `can-i`에 `yes / no`가 나온다. 토큰 문자열을 화면에 출력하거나 온라인 JWT 디코더에 보내지 않는다.

**과제:** 강사가 교육 그룹 바인딩의 `oidc:` 접두사를 빠뜨린 사례를 진단해 보자. `whoami`부터 실패하면 issuer·CA·audience·만료를 보고, `whoami`는 맞는데 `Forbidden`이면 실제 group 문자열·namespace·verb를 비교한다. RBAC를 수정한 뒤 같은 사용자로 재검사한다. 그룹 멤버십 변경은 새 ID token이 필요할 수 있다. 수업 후에는 전용 캐시 정책에 따라 로그인 세션을 종료하고 교육용 kubeconfig/임시 바인딩만 반납한다.
