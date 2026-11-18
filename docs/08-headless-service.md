# 08. Headless Service — Pod 하나하나를 직접 찾아가기

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

## 2. YAML 뜯어보기

StatefulSet(2대) + headless Service 조합입니다. 각 Pod는 접속하면 자기 호스트네임과 IP를
응답하도록 만들어서, "어느 Pod에 연결됐는지" 눈으로 확인할 수 있게 했습니다.
([examples/08-headless/sts-headless.yaml](../examples/08-headless/sts-headless.yaml))

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: edu-statefulset
spec:
  replicas: 2
  selector:
    matchLabels:
      app: edu-app
  template:
    metadata:
      labels:
        app: edu-app
    spec:
      containers:
      - name: web
        image: ubuntu/apache2:latest
        command:
          - "/bin/sh"
          - "-c"
          - >
            echo "ServerName localhost" > /etc/apache2/conf-available/server-name.conf &&
            a2enconf server-name &&
            echo "$(hostname)-$(hostname -i)" > /var/www/html/index.html &&
            apache2ctl -DFOREGROUND
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: pod-edu-service
spec:
  type: ClusterIP
  clusterIP: None            # ★ 이 한 줄이 headless 서비스를 만든다
  selector:
    app: edu-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
```

> 원본 예시에는 `nodeSelector: type: worker`가 있었습니다. 1장 실습에서 노드에 해당 레이블을
> 붙였다면 추가해도 되고, 없으면 생략해도 됩니다.

## 3. 실습 — DNS로 Pod 찾아가기

```bash
kubectl apply -f examples/08-headless/sts-headless.yaml
kubectl get svc pod-edu-service
```

```
NAME              TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
pod-edu-service   ClusterIP   None         <none>        80/TCP    61s
```

`CLUSTER-IP`가 **None** — 대표 IP가 없습니다.

### DNS 조회해 보기

쿠버네티스 내부 DNS(coredns)에 등록되는 이름 규칙:

```
서비스:  <서비스이름>.<네임스페이스>.svc.cluster.local
Pod:    <pod-ip를 -로 연결>.<네임스페이스>.pod.cluster.local
sts Pod: <pod이름>.<서비스이름>.<네임스페이스>.svc.cluster.local   ← 고정 이름!
```

```bash
# 컨테이너 안으로
kubectl exec edu-statefulset-0 -it -- bash

# 서비스 이름을 조회하면 → Pod들의 "실제 IP가 전부" 나옴 (일반 svc는 가상 IP 1개만 나옴)
root@edu-statefulset-0:/# host pod-edu-service.default.svc.cluster.local
pod-edu-service.default.svc.cluster.local has address 192.168.85.62
pod-edu-service.default.svc.cluster.local has address 192.168.85.63
```

### 개별 Pod에 직접 접속

```bash
# 내 IP 확인
root@edu-statefulset-0:/# hostname -I
192.168.85.63

# ① pod IP 기반 이름으로 접속
root@edu-statefulset-0:/# curl 192-168-85-63.default.pod.cluster.local
edu-statefulset-0-192.168.85.63

# ② 서비스 이름으로 접속 (headless라서 로드밸런싱 없이 DNS가 준 IP로 직접 연결)
root@edu-statefulset-0:/# curl pod-edu-service.default.svc.cluster.local
edu-statefulset-0-192.168.85.63

# ③ sts pod의 "고정 이름"으로 특정 Pod를 콕 집어 접속 — 실무에서 가장 중요한 패턴
root@edu-statefulset-0:/# curl edu-statefulset-1.pod-edu-service.default.svc.cluster.local
edu-statefulset-1-192.168.85.62
```

③이 핵심입니다. `edu-statefulset-1.pod-edu-service...` 라는 이름은 Pod가 재시작되어 IP가 바뀌어도
**항상 1번 Pod**를 가리킵니다. MySQL 프라이머리를 `mysql-0.mysql...` 로 지정하는 식으로 활용합니다.

## 4. 일반 Service와 비교 정리

| | 일반 Service (ClusterIP) | Headless Service |
|---|---|---|
| 가상 IP | 있음 (단일 진입점) | 없음 (`clusterIP: None`) |
| DNS 조회 결과 | 가상 IP 1개 | 모든 Pod의 실제 IP |
| 로드밸런싱 | 함 | 안 함 |
| 개별 Pod 고정 DNS | 없음 | 있음 (sts와 함께 쓸 때) |
| 용도 | 무상태 앱의 진입점 | DB/Kafka 등 멤버를 구분해야 하는 앱 |

## 5. 실습 정리

```bash
kubectl delete -f examples/08-headless/sts-headless.yaml
```

## 확인 문제

1. headless Service를 만드는 설정 한 줄은?
2. headless Service의 DNS를 조회하면 무엇이 반환되는가?
3. StatefulSet에 headless Service가 필수인 이유는?

<details><summary>정답 보기</summary>

1. `clusterIP: None`
2. 가상 IP가 아니라, 셀렉터에 걸린 모든 Pod의 실제 IP 목록
3. 각 Pod에게 `<pod이름>.<서비스이름>...` 형태의 고정 DNS 이름을 만들어 주기 위해. 이 이름이 있어야 "0번 Pod에만 접속" 같은 멤버 구분이 가능하다.
</details>

---

다음 장: [09. DaemonSet — 모든 노드에 하나씩](09-daemonset.md)
