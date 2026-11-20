# 03. Service — 바뀌는 Pod IP 대신 고정 주소로

## 1. 개념

1장에서 배웠듯 Pod는 일회용이고, 재생성될 때마다 IP가 바뀝니다.
그런데 웹 앱이 DB Pod에 접속해야 한다면? DB Pod가 재시작할 때마다 접속 주소를 고쳐야 할까요?

**Service(서비스)** 는 이 문제를 해결합니다.

- 같은 역할을 하는 Pod 그룹(레이블로 선택) 앞에 **고정된 가상 IP와 DNS 이름**을 만들어 주는 리소스
- 요청이 오면 뒤에 있는 Pod들에게 **분산(로드밸런싱)** 해서 전달
- Pod가 죽고 새로 생겨도 Service 주소는 변하지 않음 — Service가 알아서 새 Pod를 찾아 연결

Service가 Pod를 찾는 방법은 **레이블 셀렉터**입니다.
Service의 `selector`와 Pod의 `labels`가 일치해야 연결됩니다.

## 2. Service의 4가지 타입

| 타입 | 접근 범위 | 용도 |
|------|----------|------|
| **ClusterIP** (기본값) | 클러스터 **내부**에서만 | Pod끼리 통신 (앱 → DB 등) |
| **NodePort** | 클러스터 **외부**에서 노드IP:포트로 | 개발/테스트용 외부 노출 |
| **LoadBalancer** | 외부 (클라우드 로드밸런서 경유) | 클라우드 환경의 정식 외부 노출 |
| **ExternalName** | — (내부 → 외부로 나가는 별칭) | 클러스터 밖의 DB/API를 내부 DNS 이름으로 참조 |

### ClusterIP

타입을 안 쓰거나 `type: ClusterIP`로 두면 클러스터 내부 전용 가상 IP가 생깁니다.

```bash
# 클러스터 내부(노드 또는 Pod)에서는 접속됨
[root@ks1 ~]# curl 10.111.13.3
pod-edu-192.168.85.44

# 클러스터 외부 머신에서는 접속 불가
[root@ks4 ~]# curl 10.111.13.3
curl: (7) Failed connect to 10.111.13.3:80; Connection timed out
```

### NodePort

`type: NodePort`로 설정하면 **모든 노드의 특정 포트**(기본 30000~32767 범위, YAML에서 직접 지정 가능)가
이 Service로 연결됩니다. 외부에서 `노드IP:노드포트`로 접근할 수 있습니다.

```
외부 사용자 → 노드IP:30770 → Service → Pod들 (분산)
```

### ExternalName

반대 방향입니다. 클러스터 **안의** 앱이 **밖에 있는** 서비스(외부 DB, 외부 API)를 쓸 때,
외부 주소를 클러스터 내부 DNS 이름으로 감싸 줍니다.
외부 서비스의 주소가 바뀌어도 앱 코드는 그대로 두고 Service만 고치면 됩니다.

## 3. YAML 뜯어보기

([examples/03-service/svc-nodeport.yaml](../examples/03-service/svc-nodeport.yaml))

```yaml
apiVersion: v1
kind: Service
metadata:
  name: edu-service
spec:
  type: NodePort            # 생략하면 ClusterIP
  selector:
    app: edu-web            # app=edu-web 레이블이 붙은 모든 Pod가 대상
  ports:
    - protocol: TCP
      port: 80              # Service 자신의 포트 (ClusterIP:80)
      targetPort: 80        # 트래픽을 전달할 Pod(컨테이너)의 포트
      nodePort: 30080       # (NodePort 타입만) 노드에 열 포트. 생략 시 자동 할당
```

포트가 3종류라 헷갈리기 쉽습니다:

```
외부 → [노드IP:nodePort(30080)] → [Service:port(80)] → [Pod:targetPort(80)]
```

## 4. 실습 — 로드밸런싱 눈으로 확인하기

2장 Deployment(replicas=2)에 Service를 붙이고, 요청이 두 Pod로 분산되는지 확인합니다.

### 4-1. 준비

각 Pod가 "자기 이름"을 응답하도록 1장과 같은 아파치 이미지를 씁니다.
([examples/03-service/deploy-with-svc.yaml](../examples/03-service/deploy-with-svc.yaml))

```bash
kubectl apply -f examples/03-service/deploy-with-svc.yaml
kubectl get svc edu-service
```

```
NAME          TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
edu-service   NodePort   10.104.47.20    <none>        80:30080/TCP   5s
```

### 4-2. 반복 요청으로 분산 확인

```bash
# 노드 혹은 클러스터 내부에서 (CLUSTER-IP는 본인 환경 값으로)
for i in {1..6}; do curl -s 10.104.47.20; done
```

```
edu-deployment-abc123-xxxxx-192.168.85.62
edu-deployment-abc123-yyyyy-192.168.85.63
edu-deployment-abc123-xxxxx-192.168.85.62
edu-deployment-abc123-yyyyy-192.168.85.63
...
```

요청이 두 Pod를 오가는 것이 보입니다. 이것이 Service의 로드밸런싱입니다.

### 4-3. DNS 이름으로 접근하기

Service를 만들면 클러스터 내부 DNS에 이름이 자동 등록됩니다.

```
<서비스이름>.<네임스페이스>.svc.cluster.local
```

```bash
# 아무 Pod에 들어가서
kubectl exec -it <아무 pod 이름> -- bash

# IP 대신 이름으로 호출 (같은 네임스페이스면 서비스 이름만으로도 OK)
curl edu-service
curl edu-service.default.svc.cluster.local
```

실무에서는 IP가 아니라 **항상 이 DNS 이름**을 씁니다. 예를 들어 Python 앱의 DB 접속 설정은
`host = "mysql-service.default.svc.cluster.local"` 처럼 적습니다.

### 4-4. ExternalName 실습 (선택)

외부 서비스(여기선 google.com이라고 가정)를 내부 이름으로 감싸 봅니다.
([examples/03-service/svc-externalname.yaml](../examples/03-service/svc-externalname.yaml))

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-dns-service
spec:
  type: ExternalName
  externalName: google.com     # 가리킬 외부 도메인
```

```bash
kubectl apply -f examples/03-service/svc-externalname.yaml

# Pod 안에서 내부 DNS 이름으로 외부 서비스 호출
kubectl exec -it <아무 pod 이름> -- \
  curl external-dns-service.default.svc.cluster.local
```

## 5. 실습 정리

```bash
kubectl delete -f examples/03-service/deploy-with-svc.yaml
kubectl delete -f examples/03-service/svc-externalname.yaml
```

## 확인 문제

1. ClusterIP와 NodePort의 차이는?
2. Service는 어떤 기준으로 트래픽을 보낼 Pod를 찾는가?
3. 클러스터 안의 앱이 밖의 외부 DB를 내부 DNS 이름으로 쓰고 싶을 때 적합한 Service 타입은?

<details><summary>정답 보기</summary>

1. ClusterIP는 클러스터 내부에서만 접근 가능한 가상 IP, NodePort는 추가로 모든 노드의 포트(30000~32767)를 열어 외부 접근을 허용
2. 레이블 셀렉터 — Service의 `selector`와 일치하는 `labels`를 가진 Pod들
3. ExternalName
</details>

---

다음 장: [04. ConfigMap — 설정을 코드와 분리하기](04-configmap.md)
