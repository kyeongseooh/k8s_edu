# 03. Service — 바뀌는 Pod IP 대신 고정 주소로

## 1. 개념

1장에서 배웠듯 Pod는 일회용이고, 재생성될 때마다 IP가 바뀝니다.
그런데 웹 앱이 DB Pod에 접속해야 한다면? DB Pod가 재시작할 때마다 접속 주소를 고쳐야 할까요?

**Service(서비스)** 는 이 문제를 해결합니다.

- 같은 역할을 하는 Pod 그룹(레이블로 선택) 앞에 **고정된 가상 IP와 DNS 이름**을 만들어 주는 리소스
- 요청이 오면 뒤에 있는 Pod들에게 **분산(로드밸런싱)** 해서 전달
- Pod가 죽고 새로 생겨도 Service 주소는 변하지 않음 — Service가 알아서 새 Pod를 찾아 연결

Service가 Pod를 찾는 방법은 **레이블 셀렉터**입니다.
Service의 `selector`와 Pod의 `labels`가 일치해야 연결됩니다. 이 둘이 안 맞으면 Service는
"생겼지만 아무 Pod도 연결되지 않은" 껍데기가 됩니다 — 이 장의 의도적 오류 실습이 바로 그 상황입니다.

## 2. Service의 4가지 타입

| 타입 | 접근 범위 | 용도 |
|------|----------|------|
| **ClusterIP** (기본값) | 클러스터 **내부**에서만 | Pod끼리 통신 (앱 → DB 등) — 이 장의 실습은 이 타입만 실제로 다룹니다 |
| **NodePort** | 클러스터 **외부**에서 노드IP:포트로 | 개발/테스트용 외부 노출 (공용 클러스터에서는 포트 충돌 위험이 있어 개념만 설명) |
| **LoadBalancer** | 외부 (클라우드 로드밸런서 경유) | 클라우드 환경의 정식 외부 노출 |
| **ExternalName** | — (내부 → 외부로 나가는 별칭) | 클러스터 밖의 DB/API를 내부 DNS 이름으로 참조 (개념만 설명) |

### ClusterIP — 이 장의 실습 대상

타입을 안 쓰거나 `type: ClusterIP`로 두면 클러스터 내부 전용 가상 IP가 생깁니다. 클러스터 안의
노드나 다른 Pod에서는 이 IP(혹은 DNS 이름)로 접속할 수 있고, 클러스터 밖에서는 접속할 수 없습니다.

### NodePort (개념만)

```text
# 개념 참고용 — 공용 실습 클러스터에서는 포트 충돌을 피하기 위해 실제로 실행하지 않습니다.
# type: NodePort로 설정하면 "모든 노드의 특정 포트"가 이 Service로 연결됩니다.
외부 사용자 → 노드IP:30770 → Service → Pod들 (분산)
```

### ExternalName (개념만)

반대 방향입니다. 클러스터 **안의** 앱이 **밖에 있는** 서비스(외부 DB, 외부 API)를 쓸 때,
외부 주소를 클러스터 내부 DNS 이름으로 감싸 줍니다. 외부 서비스의 주소가 바뀌어도 앱 코드는
그대로 두고 Service만 고치면 됩니다. 이 실습에서는 실제 외부 서비스를 호출하지 않으므로
개념만 설명합니다. ([examples/03-service/svc-externalname.yaml](../examples/03-service/svc-externalname.yaml))

```yaml
apiVersion: v1
kind: Service
metadata:
  name: svc-edu03-ext
spec:
  type: ExternalName
  externalName: legacy-db.internal.example   # 가리킬 외부(사내) 도메인 — 예시용 가상 주소
```

## 3. YAML 뜯어보기

([examples/03-service/svc-clusterip.yaml](../examples/03-service/svc-clusterip.yaml) — 실습에서는
ClusterIP로 사용합니다)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: svc-edu03
spec:
  type: ClusterIP           # 생략해도 기본값은 ClusterIP
  selector:
    app: edu03-web          # app=edu03-web 레이블이 붙은 모든 Pod가 대상
  ports:
    - protocol: TCP
      port: 80              # Service 자신의 포트 (ClusterIP:80)
      targetPort: 80        # 트래픽을 전달할 Pod(컨테이너)의 포트
```

NodePort 타입이라면 포트가 3종류라 헷갈리기 쉽습니다 (개념 참고):

```text
외부 → [노드IP:nodePort(30080)] → [Service:port(80)] → [Pod:targetPort(80)]
```

## 4. 실습 ① — 정상: 로드밸런싱 눈으로 확인하기

2장과 비슷하게 Deployment(replicas=2)에 Service를 붙이고, 요청이 두 Pod로 분산되는지 확인합니다.
각 Pod가 1장처럼 "자기 이름-IP"를 응답하도록 nginx 이미지를 씁니다.

### 4-1. 준비

```bash
k apply -f examples/03-service/deployment.yaml
k wait --for=condition=Available deployment/deploy-edu03 --timeout=60s
k apply -f examples/03-service/svc-clusterip.yaml
k get svc svc-edu03
```

```
NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
svc-edu03    ClusterIP   10.104.47.20    <none>        80/TCP    5s
```

### 4-2. 반복 요청으로 분산 확인

```bash
ANYPOD=$(k get pod -l app=edu03-web --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
for i in $(seq 1 6); do k exec "$ANYPOD" -- wget -qO- http://svc-edu03/; echo; done | sort -u
```

```
deploy-edu03-abc123-xxxxx-10.244.1.12
deploy-edu03-abc123-yyyyy-10.244.1.13
```

같은 요청을 반복했는데 서로 다른 Pod 이름-IP가 둘 다 나오면, 요청이 두 Pod를 오가는 것입니다.
이것이 Service의 로드밸런싱입니다.

### 4-3. DNS 이름으로 접근하기

Service를 만들면 클러스터 내부 DNS에 이름이 자동 등록됩니다.

```
<서비스이름>.<네임스페이스>.svc.cluster.local
```

```bash
k exec "$ANYPOD" -- wget -qO- "http://svc-edu03.${NS}.svc.cluster.local/"
```

실무에서는 IP가 아니라 **항상 이 DNS 이름**을 씁니다. 예를 들어 Python 앱의 DB 접속 설정은
`host = "mysql-service.default.svc.cluster.local"` 처럼 적습니다.

## 5. 실습 ② — 의도적 오류: selector 오타로 "응답 없음" 재현

실무에서 "서비스는 만들었는데 아무 응답이 없어요"의 가장 흔한 원인은 **selector 오타**입니다.
([examples/03-service/svc-clusterip-broken.yaml](../examples/03-service/svc-clusterip-broken.yaml))

```yaml
spec:
  selector:
    app: edu03-wbe    # 오타! 실제 Pod 레이블은 edu03-web (의도적 오류)
```

### 5-1. 오류 재현

```bash
k apply -f examples/03-service/svc-clusterip-broken.yaml
k get svc svc-edu03
```

### 5-2. 관찰 (힌트)

```bash
k get endpoints svc-edu03
k get endpointslice -l kubernetes.io/service-name=svc-edu03
```

```
NAME        ENDPOINTS   AGE
svc-edu03   <none>      1m
```

`ENDPOINTS`가 `<none>`이면 요청을 받을 준비된 주소가 없다는 신호입니다. 이 과제에서는 Pod가 Ready인데 selector가 달라졌습니다. readiness 실패도 비슷한 증상을 낼 수 있으므로 실제 라벨과 EndpointSlice의 `conditions.ready`를 비교합니다.
Service 자체는 정상으로 "생성"되었지만(이게 더 헷갈리는 포인트입니다), 뒤에 연결된 실제 Pod가
없는 껍데기 상태입니다. 실제로 호출해 보면 응답이 오지 않습니다.

```bash
k exec "$ANYPOD" -- wget -T 3 -qO- http://svc-edu03/ || echo "연결 실패 (예상된 동작 — Endpoints 없음)"
```

```
연결 실패 (예상된 동작 — Endpoints 없음)
```

트러블슈팅 순서: ① `k get endpoints <svc>` 로 뒤에 연결된 Pod가 있는지 먼저 확인 →
② 비어 있다면 `k describe svc <svc>`로 selector 값을 확인 → ③ `k get pod --show-labels`로
실제 Pod 레이블과 비교.

### 5-3. 복구

<details><summary>조치하기 전, 원인과 수정할 대상을 먼저 설명해 보세요. 복구 방법 펼치기</summary>

```bash
k apply -f examples/03-service/svc-clusterip.yaml
```

</details>

### 5-4. 기능 검증

```bash
k get endpoints svc-edu03
k get endpointslice -l kubernetes.io/service-name=svc-edu03
for i in $(seq 1 4); do k exec "$ANYPOD" -- wget -qO- http://svc-edu03/; echo; done | sort -u
```

`ENDPOINTS`에 Pod IP 2개가 보이고, 다시 Service 이름으로 응답이 오면 복구 완료입니다. 매 요청이 반드시 번갈아 가는 것은 아닙니다.

## 6. 실습 정리

```bash
k delete -f examples/03-service/svc-clusterip.yaml --ignore-not-found
k delete -f examples/03-service/deployment.yaml --ignore-not-found
```

## 확인 문제

1. ClusterIP와 NodePort의 차이는?
2. Service는 어떤 기준으로 트래픽을 보낼 Pod를 찾는가?
3. `k get endpoints <svc이름>`의 결과가 `<none>`이면 가장 먼저 의심해 볼 것은?

<details><summary>정답 보기</summary>

1. ClusterIP는 클러스터 내부에서만 접근 가능한 가상 IP, NodePort는 추가로 모든 노드의 포트(30000~32767)를 열어 외부 접근을 허용 (단, 공용 클러스터에서는 포트 충돌에 주의해야 한다)
2. 레이블 셀렉터 — Service의 `selector`와 일치하는 `labels`를 가진 Pod들
3. Service의 `selector`와 실제 Pod의 `labels`가 안 맞는 경우 (오타 포함)
</details>

---

다음 장: [04. ConfigMap — 설정을 코드와 분리하기](04-configmap.md)
