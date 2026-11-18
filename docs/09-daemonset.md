# 09. DaemonSet — 모든 노드에 하나씩

## 1. 개념

Deployment는 "총 몇 개"를 지정하지만, 어떤 프로그램은 개수가 아니라 **"모든 노드에 하나씩"**
떠 있어야 합니다.

- 로그 수집기 (각 노드의 로그를 모아야 하니까 — Fluentd, Filebeat)
- 모니터링 에이전트 (각 노드의 CPU/메모리를 측정 — node-exporter)
- 네트워크 플러그인, 스토리지 데몬

**DaemonSet(데몬셋, 줄여서 ds)** 이 바로 이것을 해 주는 컨트롤러입니다.

- 클러스터의 **모든 워커 노드에 Pod를 1개씩** 실행
- **노드가 새로 추가되면** 그 노드에도 자동으로 Pod를 띄움
- **노드가 제거되면** 그 노드의 Pod는 (다른 데로 옮기지 않고) 함께 삭제됨
- nodeSelector 등으로 **특정 레이블의 노드에만** 실행하는 것도 가능

> **비유**: Deployment가 "매장 전체에 직원 3명"이라면, DaemonSet은 "**각 층마다** 경비원 1명"입니다.
> 층(노드)이 늘어나면 경비원도 자동으로 늘어납니다. replicas 숫자가 아예 없다는 점에 주목하세요 —
> 개수는 노드 수가 결정합니다.

## 2. YAML 뜯어보기

Fluentd(로그 수집기)를 모든 노드에 띄우는 전형적인 예시입니다.
([examples/09-daemonset/daemonset.yaml](../examples/09-daemonset/daemonset.yaml))

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd-elasticsearch
  namespace: kube-system        # ① 시스템 성격의 앱이라 kube-system 네임스페이스에
  labels:
    k8s-app: fluentd-logging    # ② DaemonSet 자체에 붙는 레이블
spec:
  selector:
    matchLabels:
      name: fluentd-elasticsearch
  updateStrategy:
    type: RollingUpdate         # ③ 이미지 변경 시 노드별로 하나씩 교체
  template:
    metadata:
      labels:
        name: fluentd-elasticsearch
    spec:
      containers:
      - name: fluentd-elasticsearch
        image: quay.io/fluentd_elasticsearch/fluentd:v2.5.2   # ④
        env:
        - name: testenv
          value: value
        resources:              # 노드마다 뜨는 만큼 자원 제한을 걸어 주는 게 좋음
          limits:
            memory: 200Mi
          requests:
            cpu: 100m           # 100m = 0.1 코어
            memory: 200Mi
```

구조는 Deployment와 거의 같고, **`replicas`가 없다**는 게 가장 큰 차이입니다.

> **네임스페이스(namespace)란?** 클러스터 안의 리소스를 묶는 "폴더" 같은 개념입니다.
> 지금까지 우리가 만든 것들은 전부 `default` 네임스페이스에 생겼고, 쿠버네티스 시스템 구성 요소는
> `kube-system`에 있습니다. `-n <이름>` 옵션으로 네임스페이스를 지정해 조회합니다.

## 3. 실습 — 노드 수만큼 Pod가 생기는지 확인

```bash
kubectl apply -f examples/09-daemonset/daemonset.yaml

# kube-system 네임스페이스에서, 어느 노드에 떴는지(-owide)까지 확인
kubectl get pod -n kube-system -owide | grep fluentd
```

```
fluentd-elasticsearch-qqg5c   1/1   Running   0   15s   192.168.85.51    ks3.dd.io
fluentd-elasticsearch-z6f6h   1/1   Running   0   20s   192.168.118.38   ks2.dd.io
```

워커 노드(ks2, ks3)마다 정확히 1개씩 생겼습니다.

> **왜 컨트롤 플레인(ks1)에는 안 떴을까?** 컨트롤 플레인 노드에는 보통 **taint**(오염 표시)가
> 붙어 있어서 일반 Pod가 스케줄되지 않습니다. 시스템 데몬셋들은 toleration(관용 설정)을 달아서
> 컨트롤 플레인에도 뜹니다. 지금은 "그런 장치가 있다" 정도만 알아 두세요.

```bash
# DaemonSet 자체의 상태 보기
kubectl get ds -n kube-system fluentd-elasticsearch
```

```
NAME                    DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE
fluentd-elasticsearch   2         2         2       2            2           <none>          1m
```

DESIRED(원하는 개수)가 replicas가 아니라 **노드 수에 의해** 2로 정해져 있는 것을 볼 수 있습니다.

### 특정 노드에서만 실행하기 (선택)

1장에서 배운 nodeSelector를 template에 넣으면 됩니다.

```yaml
  template:
    spec:
      nodeSelector:
        type: "worker"       # 이 레이블이 붙은 노드에만 데몬 Pod 생성
```

## 4. 실습 정리

```bash
kubectl delete -f examples/09-daemonset/daemonset.yaml
```

## 확인 문제

1. DaemonSet에 replicas 설정이 없는 이유는?
2. 노드가 클러스터에 새로 추가되면 DaemonSet은 어떻게 동작하는가?
3. 다음 중 DaemonSet이 적합한 것은? (a) 웹 API 서버 (b) 노드 메트릭 수집기 (c) MySQL

<details><summary>정답 보기</summary>

1. Pod 개수가 "노드 수"로 자동 결정되기 때문 (노드당 1개)
2. 새 노드에 자동으로 Pod를 1개 띄운다. 반대로 노드가 제거되면 그 Pod는 삭제된다(이동하지 않음).
3. (b) — 모든 노드에서 하나씩 돌아야 하는 에이전트. (a)는 Deployment, (c)는 StatefulSet.
</details>

---

다음 장: [10. Ingress — 하나의 입구로 여러 서비스 노출하기](10-ingress.md)
