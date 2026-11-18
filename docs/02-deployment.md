# 02. Deployment — Pod를 지키고, 늘리고, 무중단으로 바꾸는 관리자

## 1. 개념

1장에서 만든 Pod에는 치명적인 약점이 있습니다. **죽으면 끝**이라는 점입니다.
노드가 고장 나거나 실수로 삭제하면 아무도 되살려 주지 않습니다.

**Deployment(디플로이먼트)** 는 Pod를 대신 관리해 주는 상위 리소스입니다.

- Pod 개수를 **보장**한다 — "3개 유지해 줘"라고 선언하면, 하나가 죽어도 자동으로 다시 만들어 3개를 맞춘다
- **롤링 업데이트(rolling update)** — 새 버전 배포 시 Pod를 하나씩 교체해서 서비스 중단이 없다
- **롤백(rollback)** — 새 버전에 문제가 있으면 이전 버전으로 되돌릴 수 있다

내부적으로 Deployment는 **ReplicaSet**이라는 중간 관리자를 만들고, ReplicaSet이 Pod 개수를 유지합니다.

![Deployment > ReplicaSet > Pod 구조](../images/02-deployment-diagram.png)

```
Deployment  →  ReplicaSet  →  Pod, Pod, Pod
(배포 전략/이력 관리)   (개수 유지)      (실제 실행)
```

> **Python 비유**: `while True:` 루프 안에서 자식 프로세스 수를 감시하다가,
> 죽은 게 보이면 다시 `subprocess.Popen()` 해 주는 감시 스크립트를 쿠버네티스가 내장해 둔 것이라고
> 생각하면 됩니다. 우리는 "몇 개를 유지할지"만 선언하면 됩니다.

실무에서는 **Pod를 직접 만들 일이 거의 없고, 대부분 Deployment로 만듭니다.**

## 2. YAML 뜯어보기

웹 서버를 Deployment로 띄우고 Service까지 함께 정의한 예시입니다.
([examples/02-deployment/deploy-edu.yaml](../examples/02-deployment/deploy-edu.yaml))

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: edu-deployment
spec:
  replicas: 2                  # Pod를 몇 개 유지할 것인가
  selector:                    # "어떤 Pod가 내 관리 대상인가"를 레이블로 지정
    matchLabels:
      app: edu-web             # ← 아래 template의 레이블과 반드시 일치해야 함!
  template:                    # 여기서부터는 "Pod를 찍어낼 틀" (1장의 Pod 정의와 동일한 구조)
    metadata:
      labels:
        app: edu-web           # 찍혀 나오는 Pod마다 이 레이블이 붙음
    spec:
      containers:
        - name: web
          image: ubuntu/apache2:latest
          ports:
            - containerPort: 80
---                            # '---' 는 한 파일에 여러 리소스를 적는 구분선
apiVersion: v1
kind: Service
metadata:
  name: edu-service
spec:
  selector:
    app: edu-web               # app=edu-web 레이블이 붙은 Pod들에게 트래픽 전달
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
  type: NodePort
```

**핵심 연결 고리**: `selector.matchLabels` = `template.metadata.labels` = Service의 `selector`.
세 곳의 레이블이 맞아야 "Deployment가 Pod를 관리하고, Service가 그 Pod들을 찾는" 체인이 완성됩니다.

## 3. 실습 ① — 자동 복구(self-healing) 체험

```bash
kubectl apply -f examples/02-deployment/deploy-edu.yaml
kubectl get deploy,rs,pod
```

```
NAME                             READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/edu-deployment   2/2     2            2           20s

NAME                                        DESIRED   CURRENT   READY   AGE
replicaset.apps/edu-deployment-6c7cbd7b6    2         2         2       20s

NAME                                  READY   STATUS    RESTARTS   AGE
pod/edu-deployment-6c7cbd7b6-nlt55    1/1     Running   0          20s
pod/edu-deployment-6c7cbd7b6-s2jgm    1/1     Running   0          20s
```

Deployment 하나로 ReplicaSet과 Pod 2개가 줄줄이 생긴 게 보입니다.
Pod 이름의 `6c7cbd7b6-nlt55` 같은 부분은 자동으로 붙는 랜덤 해시입니다.

이제 Pod 하나를 **일부러 죽여 봅시다.**

```bash
kubectl delete pod edu-deployment-6c7cbd7b6-nlt55   # 이름은 본인 환경 것으로
kubectl get pod
```

```
NAME                              READY   STATUS    RESTARTS   AGE
edu-deployment-6c7cbd7b6-s2jgm    1/1     Running   0          3m
edu-deployment-6c7cbd7b6-x9k2p    1/1     Running   0          5s    ← 새로 생김!
```

삭제하자마자 새 Pod가 즉시 생성됩니다. "replicas: 2를 유지하라"는 선언을 쿠버네티스가 지키는 것입니다.

### Pod 개수 조절 (스케일링)

```bash
kubectl scale deployment edu-deployment --replicas=4
kubectl get pod            # 4개로 늘어남
kubectl scale deployment edu-deployment --replicas=2
```

## 4. 실습 ② — 롤링 업데이트와 롤백

### 4-1. 업데이트 이력 확인

```bash
kubectl rollout history deployment edu-deployment
```

```
REVISION  CHANGE-CAUSE
1         <none>
```

`CHANGE-CAUSE`(변경 사유)는 기본으로 비어 있습니다. `--record` 옵션을 붙여 적용하면 실행한 명령이 기록됩니다.

```bash
kubectl apply -f examples/02-deployment/deploy-edu.yaml --record
```

> `--record`는 최신 버전에서 deprecated 경고가 뜨지만 여전히 동작합니다. 대안으로
> `kubectl annotate deployment edu-deployment kubernetes.io/change-cause="v2 배포"` 를 쓸 수 있습니다.

### 4-2. 이미지 교체 (롤링 업데이트)

컨테이너 이미지를 다른 버전으로 바꿔 봅니다. 형식: `kubectl set image deploy <디플로이먼트> <컨테이너이름>=<새이미지>`

```bash
kubectl set image deploy edu-deployment web=ubuntu/apache2:2.4-22.04_beta --record

# 교체 과정을 실시간으로 관찰
kubectl rollout status deployment edu-deployment
```

이때 Pod가 **한꺼번에 꺼지지 않고 하나씩 교체**됩니다. 새 Pod가 Ready 되면 옛 Pod를 끄는 식이라
서비스가 끊기지 않습니다. 이것이 롤링 업데이트입니다.

```bash
kubectl rollout history deployment edu-deployment
```

```
REVISION  CHANGE-CAUSE
1         kubectl apply --filename=deploy-edu.yaml --record=true
2         kubectl set image deploy edu-deployment web=ubuntu/apache2:2.4-22.04_beta --record=true
```

### 4-3. 롤백

새 버전에 버그가 있다면? 한 줄로 되돌립니다.

```bash
# 바로 직전 버전으로
kubectl rollout undo deployment edu-deployment

# 특정 리비전으로
kubectl rollout undo deployment edu-deployment --to-revision=1
```

```
deployment.apps/edu-deployment rolled back
```

롤백도 롤링 방식으로 진행되어 무중단입니다.

## 5. 실습 정리

```bash
kubectl delete -f examples/02-deployment/deploy-edu.yaml
```

> **팁**: `apply -f`로 만든 것은 `delete -f`로 한 번에 지울 수 있습니다. 파일에 정의된
> 리소스(Deployment + Service)가 모두 삭제됩니다.

## 확인 문제

1. replicas: 3인 Deployment에서 Pod 하나를 `kubectl delete pod`로 지우면 어떻게 되는가?
2. Deployment와 Pod 사이에 있는 중간 관리자의 이름은?
3. 롤링 업데이트가 "무중단"인 이유는?

<details><summary>정답 보기</summary>

1. ReplicaSet이 개수 부족(2 < 3)을 감지하고 즉시 새 Pod를 만들어 3개를 복구한다. Pod를 정말 없애려면 Deployment 자체를 지우거나 replicas를 줄여야 한다.
2. ReplicaSet
3. 새 Pod를 먼저 띄워 준비시킨 뒤 옛 Pod를 하나씩 제거하므로, 교체 중에도 항상 요청을 받을 Pod가 살아 있기 때문
</details>

---

다음 장: [03. Service — 바뀌는 Pod IP 대신 고정 주소로](03-service.md)
