# 07. StatefulSet — 이름과 데이터가 유지되어야 하는 앱

## 1. 개념

Deployment는 Pod들을 "모두 똑같은 일회용"으로 취급합니다. 웹 서버처럼 어느 Pod가 응답해도
상관없는(**무상태, stateless**) 앱에는 완벽하지만, DB처럼 각자 **자기 데이터와 정체성**을 가져야 하는
(**유상태, stateful**) 앱에는 맞지 않습니다.

**StatefulSet(스테이트풀셋, 줄여서 sts)** 은 Pod의 **상태를 유지해 주는** 컨트롤러입니다.

- **Pod 이름이 고정**: `web-0`, `web-1`, `web-2` 처럼 번호가 붙고, 재시작해도 같은 이름 유지
- **Pod마다 전용 볼륨**: `volumeClaimTemplates`로 Pod별 PVC가 자동 생성되고, 재시작해도 자기 볼륨에 다시 연결
- **순서 보장**: 0번부터 차례로 생성, 역순으로 종료

> **비유**: Deployment의 Pod들은 "교대 근무 아르바이트"(아무나 대체 가능),
> StatefulSet의 Pod들은 "각자 자기 사물함(볼륨)과 사번(이름)이 있는 정직원"입니다.
> MySQL 클러스터에서 "0번이 프라이머리, 1·2번이 레플리카" 같은 역할 구분이 가능해집니다.

### Deployment와 비교해 보기

Deployment의 Pod 이름은 랜덤 해시가 붙고, 재시작하면 바뀝니다.

```
nerfstudio-viewer-deployment-6c7cbd7b6-s2jgm    ← 재시작하면 뒷부분이 바뀜
el-trigger-eventlistner-6cc8c7c5fc-hqw7x
```

StatefulSet의 Pod는 `-0`, `-1`, `-2` 번호가 붙고 유지됩니다.

```
keycloak-0              ← 재시작해도 keycloak-0
keycloak-postgresql-0
```

## 2. YAML 뜯어보기

nginx 3대를 각자 전용 볼륨과 함께 띄우는 예시입니다.
([examples/07-statefulset/sts-web.yaml](../examples/07-statefulset/sts-web.yaml))

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  selector:
    matchLabels:
      app: nginx              # template의 레이블과 일치해야 함
  serviceName: "nginx"        # ★ sts 전용: 연결할 (headless) Service 이름. 8장에서 설명
  replicas: 3
  minReadySeconds: 10         # Pod가 Ready 후 10초 지나야 "가용"으로 간주
  template:
    metadata:
      labels:
        app: nginx
    spec:
      terminationGracePeriodSeconds: 10   # 종료 신호 후 10초의 정리 시간
      containers:
      - name: nginx
        image: registry.k8s.io/nginx-slim:0.8
        ports:
        - containerPort: 80
          name: web
        volumeMounts:
        - name: www                       # 아래 volumeClaimTemplates와 매칭
          mountPath: /usr/share/nginx/html
  volumeClaimTemplates:       # ★ sts 전용: Pod마다 이 틀로 PVC를 자동 생성
  - metadata:
      name: www
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: "nfs-client"      # 환경에 맞게 변경 (minikube: standard)
      resources:
        requests:
          storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: nginx                 # 위 serviceName과 일치
  labels:
    app: nginx
spec:
  ports:
  - port: 80
    name: web
  clusterIP: None             # ★ headless 서비스 (8장)
  selector:
    app: nginx
```

Deployment와 다른 포인트 2가지만 기억하세요.

1. `serviceName` + headless Service가 **필수** — Pod 하나하나에 고정 DNS 이름을 주기 위해 (8장)
2. `volumeClaimTemplates` — Pod별 전용 PVC를 찍어내는 틀

## 3. 실습 ① — 이름/볼륨이 유지되는지 확인

```bash
kubectl apply -f examples/07-statefulset/sts-web.yaml
kubectl get pod -w        # -w: 변화를 실시간으로 지켜보기 (Ctrl+C로 종료)
```

```
web-0   1/1   Running   0   2m24s
web-1   1/1   Running   0   114s
web-2   1/1   Running   0   74s
```

- 이름이 `web-0`, `web-1`, `web-2` 로 **순서대로** 생성됩니다 (0이 Ready 돼야 1이 시작).

PVC도 Pod마다 하나씩, `<볼륨이름>-<Pod이름>` 규칙으로 자동 생성됩니다.

```bash
kubectl get pvc | grep web
```

```
www-web-0   Bound   pvc-fe4c5bfa-...   1Gi   RWO   nfs-client
www-web-1   Bound   pvc-5938c1ba-...   1Gi   RWO   nfs-client
www-web-2   Bound   pvc-475d4b0c-...   1Gi   RWO   nfs-client
```

### 정체성 유지 테스트

```bash
# web-0의 볼륨에 데이터 기록
kubectl exec web-0 -- sh -c "echo 'web-0의 데이터' > /usr/share/nginx/html/index.html"

# web-0 삭제 → 같은 이름으로 재생성됨
kubectl delete pod web-0
kubectl get pod       # web-0이 다시 생김 (web-3이 아니라!)

# 데이터도 그대로 (같은 PVC www-web-0에 다시 연결됐기 때문)
kubectl exec web-0 -- cat /usr/share/nginx/html/index.html
# web-0의 데이터
```

**이름도, 데이터도 유지**됩니다. 이것이 StatefulSet의 존재 이유입니다.

## 4. 실습 ② — 롤링 업데이트와 롤백

StatefulSet도 Deployment처럼 롤링 업데이트/롤백이 됩니다. (단, 높은 번호부터 역순으로 교체)

```bash
# 이미지 태그를 0.8 → 0.9 로 수정 (편집기가 열림: image 줄을 찾아 변경 후 저장)
kubectl edit sts web

# 업데이트 이력 확인
kubectl rollout history statefulset web
```

```
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
```

```bash
# 적용된 이미지 확인
kubectl describe pod web-0 | grep -i image:
#   Image: registry.k8s.io/nginx-slim:0.9

# 롤백
kubectl rollout undo sts web
# statefulset.apps/web rolled back
```

## 5. 그래서 언제 무엇을 쓰나?

| | Deployment | StatefulSet |
|---|---|---|
| Pod 이름 | 랜덤, 재시작 시 변경 | 번호 고정 (`-0`, `-1`...) |
| 볼륨 | 공유하거나 없음 | Pod별 전용 PVC |
| 생성 순서 | 동시에 | 순서대로 |
| 적합한 앱 | 웹 서버, API, 워커 | DB(MySQL, PostgreSQL), Kafka, ZooKeeper, Redis 등 |

**"Pod가 서로 구분되어야 하고, 각자 데이터를 가진다"** → StatefulSet. 그 외에는 Deployment.

## 6. 실습 정리

```bash
kubectl delete -f examples/07-statefulset/sts-web.yaml
# 주의: PVC는 sts를 지워도 남습니다 (데이터 보호 목적). 실습 후엔 직접 삭제
kubectl delete pvc www-web-0 www-web-1 www-web-2
```

## 확인 문제

1. StatefulSet의 Pod `web-1`을 삭제하면 새 Pod의 이름은?
2. `volumeClaimTemplates`가 하는 일은?
3. MySQL을 쿠버네티스에 올린다면 Deployment와 StatefulSet 중 무엇이 맞을까? 이유는?

<details><summary>정답 보기</summary>

1. `web-1` — 같은 이름으로 재생성되고, 기존 PVC(www-web-1)에 다시 연결된다.
2. Pod마다 전용 PVC를 자동 생성하는 틀. `<template이름>-<pod이름>` 규칙으로 만들어진다.
3. StatefulSet. DB는 데이터(전용 볼륨)와 정체성(프라이머리/레플리카 역할 구분)이 유지되어야 하기 때문.
</details>

---

다음 장: [08. Headless Service — Pod 하나하나를 직접 찾아가기](08-headless-service.md)
