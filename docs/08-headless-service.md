# 08. Headless Service — Pod 하나하나를 직접 찾아가기

## 0. 이 장의 전제

00장에서 설정한 `EDU_CONTEXT`, `NS`, `k()`를 그대로 씁니다. 이 장도 PV/PVC는 쓰지 않습니다
(7장과 마찬가지로 emptyDir 없이, DNS만 확인하면 되는 가벼운 웹 서버로 실습합니다).

```bash
k auth can-i create statefulsets.apps
k auth can-i create services
```

## 1. 개념

3장의 일반 Service는 "대표 전화번호" 하나(ClusterIP)를 주고, 걸려온 요청을 뒤의 Pod들에게
아무나 연결해 줍니다. 그런데 이런 경우는 어떨까요?

- DB 클러스터에서 "쓰기는 **반드시 0번(프라이머리)** 에게" 보내야 할 때
- ZooKeeper처럼 멤버들이 **서로의 주소를 직접 알아야** 할 때

대표번호(로드밸런싱)가 오히려 방해가 됩니다. **특정 Pod를 콕 집어** 호출해야 하니까요.

**Headless Service(헤드리스 서비스)** 는 이름 그대로 "머리(ClusterIP)가 없는" 서비스입니다.

- `clusterIP: None` 으로 설정하면 됨
- 단일 진입점(가상 IP)을 만들지 않고, **로드밸런싱도 하지 않음**
- 대신 DNS를 조회하면 **연결된 Pod들의 실제 IP가 전부** 반환됨
- StatefulSet의 각 Pod에게 **고정된 개별 DNS 이름**을 만들어 줌 (sts에 headless가 필수인 이유)

> **비유**: 일반 Service는 콜센터 대표번호(아무 상담원이나 연결),
> headless Service는 **사내 전화번호부**(각자의 내선번호가 그대로 공개)입니다.

주로 StatefulSet과 함께, HA 구성한 DB / Kafka / ZooKeeper / NiFi 등에서 사용합니다.

**핵심 메커니즘**: 이 "전화번호부"는 CoreDNS가 **Service의 Endpoints(= selector에 걸린 Pod
목록)** 를 읽어서 만듭니다. 즉, Service의 `selector`가 Pod의 `labels`와 맞지 않으면 Endpoints가
비고, **개별 Pod DNS 이름도 함께 망가집니다.** 이 장의 실습에서 이 연결을 직접 끊어 보고 복구합니다.

## 2. YAML 뜯어보기

StatefulSet(2대) + headless Service 조합입니다. 각 Pod는 접속하면 자기 호스트네임을
응답하도록 만들어서, "어느 Pod에 연결됐는지" 확인할 수 있게 했습니다.
([examples/08-headless/sts-headless.yaml](../examples/08-headless/sts-headless.yaml))

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ch08-app
spec:
  replicas: 2
  serviceName: ch08-svc
  selector:
    matchLabels:
      app: ch08-app
  template:
    metadata:
      labels:
        app: ch08-app          # ★ 아래 Service의 selector와 일치해야 DNS가 동작함
    spec:
      containers:
      - name: web
        image: nginx:1.27-alpine
        imagePullPolicy: IfNotPresent
        command:
          - "/bin/sh"
          - "-c"
          - "echo \"$(hostname)\" > /usr/share/nginx/html/index.html && nginx -g 'daemon off;'"
        ports:
        - containerPort: 80
          name: web
---
apiVersion: v1
kind: Service
metadata:
  name: ch08-svc
spec:
  clusterIP: None            # ★ 이 한 줄이 headless 서비스를 만든다
  selector:
    app: ch08-app            # ★ 위 template의 labels와 일치해야 함
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
```

## 3. 실습 — 정상 기준: DNS로 Pod 찾아가기

```bash
k apply -f examples/08-headless/sts-headless.yaml
k rollout status statefulset/ch08-app --timeout=120s
k get svc ch08-svc
k get endpoints ch08-svc
```

```
NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
ch08-svc   ClusterIP   None         <none>        80/TCP    40s

NAME       ENDPOINTS                           AGE
ch08-svc   192.168.x.11:80,192.168.x.12:80     40s
```

`CLUSTER-IP`가 **None**이고, `ENDPOINTS`에 Pod 2개의 실제 IP가 모두 보입니다 — 이것이
"전화번호부"의 내용물입니다.

쿠버네티스 내부 DNS(coredns)에 등록되는 이름 규칙:

```
서비스:   <서비스이름>.<네임스페이스>.svc.cluster.local         → Endpoints의 모든 IP
sts Pod:  <pod이름>.<서비스이름>.<네임스페이스>.svc.cluster.local → 그 Pod 하나의 IP (고정 이름!)
(DNS 도메인이 cluster.local인 환경 기준. 일반적으로 Ready한 주소가 게시된다.)
```

```bash
# 서비스 이름 조회 → Pod들의 "실제 IP가 전부" 나옴 (일반 svc는 가상 IP 1개만 나옴)
k exec ch08-app-0 -- nslookup "ch08-svc.${NS}.svc.cluster.local"

# sts pod의 "고정 이름"으로 특정 Pod를 콕 집어 조회 — 실무에서 가장 중요한 패턴
k exec ch08-app-0 -- nslookup "ch08-app-1.ch08-svc.${NS}.svc.cluster.local"

# 실제로 접속도 해본다
k exec ch08-app-0 -- wget -qO- "http://ch08-app-1.ch08-svc.${NS}.svc.cluster.local"
```

```
ch08-app-1
```

`ch08-app-1.ch08-svc...` 라는 이름은 Pod가 재시작되어 IP가 바뀌어도 **항상 1번 Pod**를
가리킵니다. 멤버에 다시 접속할 때 활용합니다. ordinal 0이라는 이유로 DB의 현재 프라이머리라고 단정하지 않습니다.

## 4. 오류 주입 — Service selector 오타로 DNS 끊기

관리자가 Service를 고치다가 `selector`에 오타를 낸 상황을 재현합니다.

```bash
k patch svc ch08-svc --type merge -p '{"spec":{"selector":{"app":"ch08-app-WRONG"}}}'
k get endpoints ch08-svc
```

```
NAME       ENDPOINTS   AGE
ch08-svc   <none>      2m
```

**관찰**: Endpoints가 완전히 비었습니다. selector가 더 이상 어떤 Pod의 labels와도 맞지 않기
때문입니다.

DNS 응답은 캐시된다. selector를 바꾼 직후 IP가 **아직 나온다고 해서 정상인 것은 아니다.** EndpointSlice가 먼저 비고 TTL이 지나면 고정 이름으로도 새 요청을 보낼 수 없다. 기본 DNS 도메인이 다르면 아래 `cluster.local`을 환경 값으로 바꾼다. 맨 끝의 점은 검색 접미사를 붙이지 않는 절대 이름이라는 뜻이다.

```bash
peer="ch08-app-1.ch08-svc.${NS}.svc.cluster.local."
peer_http() { k exec ch08-app-0 -- wget -T 2 -qO- "http://$peer/"; }
for i in {1..25}; do if ! peer_http; then break; fi; sleep 2; done
k exec ch08-app-0 -- nslookup "$peer" || true
k get endpointslice -l kubernetes.io/service-name=ch08-svc -o yaml
```

DNS 오류(`NXDOMAIN` 또는 주소 없음)와 비어 있는 대상 목록이 증거다. 반대로 실제 Pod IP로는 계속 HTTP 응답을 얻을 수 있다. 주소를 영구 설정하지 말고 진단에만 쓴다.

```bash
pod_ip=$(k get pod ch08-app-1 -o jsonpath='{.status.podIP}')
k exec ch08-app-0 -- wget -T 3 -qO- "http://$pod_ip/"
```

## 5. 힌트와 복구

<details><summary>힌트와 복구</summary>

Service의 selector와 Pod(StatefulSet template)의 labels를 나란히 비교합니다.

```bash
k get svc ch08-svc -o jsonpath='{.spec.selector}{"\n"}'
k get pod ch08-app-0 --show-labels
```

```
{"app":"ch08-app-WRONG"}
NAME         ...   LABELS
ch08-app-0   ...   app=ch08-app,...
```

`app=ch08-app-WRONG` ≠ `app=ch08-app` — 원래 값으로 되돌립니다.

```bash
k patch svc ch08-svc --type merge -p '{"spec":{"selector":{"app":"ch08-app"}}}'
k get endpoints ch08-svc
```

```
NAME       ENDPOINTS                           AGE
ch08-svc   192.168.x.11:80,192.168.x.12:80     5m
```

Endpoints가 다시 채워지면 복구된 것입니다.
</details>

## 6. 기능 확인

```bash
reply=
for i in {1..25}; do
  if k exec ch08-app-0 -- nslookup -type=A "$peer" && reply=$(peer_http) && [[ $reply == ch08-app-1 ]]; then break; fi
  sleep 2
done
printf '고정 주소의 응답: %s\n' "$reply"
[[ $reply == ch08-app-1 ]]
```

```
ch08-app-1
```

서비스 이름 조회와 "특정 Pod 콕 집기" 조회가 모두 복구되면 기능 확인이 끝난 것입니다.

## 7. 일반 Service와 비교 정리

| | 일반 Service (ClusterIP) | Headless Service |
|---|---|---|
| 가상 IP | 있음 (단일 진입점) | 없음 (`clusterIP: None`) |
| DNS 조회 결과 | 가상 IP 1개 | 모든 Pod의 실제 IP |
| 로드밸런싱 | 함 | 안 함 |
| 개별 Pod 고정 DNS | 없음 | 있음 (sts와 함께 쓸 때) |
| selector가 틀리면 | 트래픽이 전달 안 됨 | 트래픽뿐 아니라 **DNS 자체**가 끊김 |
| 용도 | 무상태 앱의 진입점 | DB/Kafka 등 멤버를 구분해야 하는 앱 |

## 8. 실습 정리

```bash
k delete -f examples/08-headless/sts-headless.yaml --ignore-not-found
```

## 확인 문제

1. headless Service를 만드는 설정 한 줄은?
2. Service의 `selector`가 Pod의 `labels`와 맞지 않으면 headless Service의 DNS는 어떻게 되는가?
3. selector를 고친 직후에도 이름 기반 호출이 실패하는 이유는?

<details><summary>정답 보기</summary>

1. `clusterIP: None`
2. 준비된 대상 주소가 사라지고 DNS 캐시가 만료되면 사용할 주소를 얻지 못한다.
3. DNS가 이전 실패 응답도 잠시 캐시할 수 있다. EndpointSlice와 Pod 직접 호출로 나눠 확인한다.
</details>

---

다음 장: [09. DaemonSet — 모든 노드에 하나씩](09-daemonset.md)
