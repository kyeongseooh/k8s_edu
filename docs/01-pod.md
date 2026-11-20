# 01. Pod — 쿠버네티스의 최소 실행 단위

## 1. 개념

**Pod(파드)** 는 쿠버네티스에서 컨테이너를 실행하는 가장 작은 단위입니다.
"컨테이너를 실행해 줘"라고 쿠버네티스에 요청할 때, 컨테이너를 직접 띄우는 게 아니라
컨테이너를 **Pod라는 포장지**에 싸서 띄웁니다.

Pod에 대해 꼭 알아야 할 성질 3가지:

1. **Pod 하나에 컨테이너가 n개 들어갈 수 있다.** (보통은 1개)
   같은 Pod 안의 컨테이너들은 네트워크를 공유해서, 같은 IP·같은 포트 공간을 씁니다.
   같은 집에 사는 가족이 주소 하나를 공유하는 것과 같습니다.
2. **Pod는 자기만의 IP를 가진다.**
3. **Pod가 재생성되면 IP가 바뀐다.** (호스트네임은 보통 Pod 이름과 같은데, 이름을 그대로
   다시 쓰면 호스트네임도 그대로입니다. 반대로 2장에서 볼 Deployment처럼 매번 **새 이름**으로
   Pod를 찍어내는 경우에는 이름이 바뀌니 호스트네임도 매번 바뀝니다.)
   Pod는 언제든 죽고 다시 만들어질 수 있는 '일회용' 존재입니다.
   그래서 고정된 주소로 접근하려면 Service(3장)가 필요합니다.

> **Python 비유**: Pod는 실행 중인 프로세스와 비슷합니다. `python app.py`를 죽이고 다시 실행하면
> PID가 바뀌듯, Pod도 다시 만들어지면 IP가 바뀝니다. "PID를 외워서 접근"하면 안 되는 것처럼
> "Pod IP를 외워서 접근"하면 안 됩니다.

## 2. 실습 준비

00장에서 각자 고유한 네임스페이스가 `NS` 환경변수로 이미 준비되어 있고, `k()` 함수
(`kubectl -n "${NS:?}" "$@"`)도 정의되어 있습니다. 이 교재의 모든 네임스페이스 범위 명령은
`kubectl` 대신 `k`를 씁니다. 이번 장에서 네임스페이스를 새로 만들거나 지우지 않습니다 —
그냥 이미 있는 `$NS`를 그대로 씁니다.

```bash
# 확인만 (별도로 만들 필요 없음)
echo "현재 네임스페이스: $NS"
kubectl get namespace "$NS"
```

## 3. YAML 뜯어보기

아래는 nginx 웹 서버 한 대를 띄우는 Pod 정의입니다. ([examples/01-pod/pod-edu.yaml](../examples/01-pod/pod-edu.yaml))

```yaml
apiVersion: v1          # 이 리소스가 속한 API 버전. Pod는 v1
kind: Pod               # 리소스 종류: Pod를 만들겠다
metadata:
  name: pod-edu01       # Pod 이름 (클러스터에서 이 이름으로 조회/삭제)
  labels:
    app: edu01-web      # 레이블: 분류용 꼬리표 (아래 6절 참고)
spec:                   # "원하는 상태"의 본문
  containers:           # 이 Pod에 담을 컨테이너 목록 (리스트)
  - name: web           # 컨테이너 이름
    image: nginx:1.27-alpine        # 사용할 이미지 (경량 nginx, wget/sh 포함)
    imagePullPolicy: IfNotPresent   # 이미 노드에 이미지가 있으면 다시 받지 않음
    command:            # 컨테이너가 시작될 때 실행할 명령
      - "/bin/sh"
      - "-c"
      - >               # '>' 는 여러 줄을 한 줄로 이어주는 YAML 문법
        echo "$(hostname)-$(hostname -i)" > /usr/share/nginx/html/index.html &&
        nginx -g 'daemon off;'
    ports:
    - containerPort: 80 # 컨테이너가 사용하는 포트 (문서 성격이 강함)
```

`command` 부분이 하는 일: 웹 서버 첫 페이지(index.html)에 **자기 호스트네임과 IP**를 적어 놓습니다.
나중에 접속했을 때 "내가 어느 Pod에 접속했는지" 눈으로 확인하기 위한 장치입니다.

## 4. 실습 ① — 정상: Pod 띄우고 접속해 보기

### 4-1. Pod 생성

```bash
k apply -f examples/01-pod/pod-edu.yaml
```

```
pod/pod-edu01 created
```

> `kubectl create -f`도 되지만, `apply`는 "없으면 만들고 있으면 수정"이라 보통 apply를 씁니다.

### 4-2. 상태 확인

```bash
k wait --for=condition=Ready pod/pod-edu01 --timeout=60s
k get pod pod-edu01
```

```
NAME        READY   STATUS    RESTARTS   AGE
pod-edu01   1/1     Running   0          10s
```

- `READY 1/1`: 컨테이너 1개 중 1개 준비됨
- `STATUS Running`: 실행 중. (`ContainerCreating`이면 이미지 내려받는 중이니 잠시 기다리세요)

### 4-3. 기능 검증 — 실제로 응답하는지 확인

Pod IP는 클러스터 안에서만 통하므로, 컨테이너 안에서 직접 호출해 내용을 확인합니다
(밖에서/다른 Pod에서 접근하는 고정 주소 이야기는 3장 Service에서 제대로 다룹니다).

```bash
k exec pod-edu01 -- wget -qO- http://127.0.0.1/
```

```
pod-edu01-10.244.1.23
```

자기 호스트네임-IP가 그대로 찍히면 정상입니다. (`localhost`는 환경에 따라 IPv6(`::1`)로 먼저
풀려 연결이 거부될 수 있어, 항상 `127.0.0.1`처럼 명시적인 IPv4 주소로 호출하는 습관을 들이세요.)

### 4-4. (참고) 외부 노출은 어떻게 하나

여러 사람이 같은 클러스터를 함께 쓰는 공용 실습 환경에서는 `NodePort`로 노드 포트를 직접 여는
실습을 전원이 동시에 하면 포트가 꼬이기 쉽습니다. 그래서 이 교재에서는 "Pod/컨테이너 안에서
직접 호출해 확인"하는 방식만 실제로 실행하고, NodePort로 외부에 노출하는 방법은 **개념**으로만
짚고 넘어갑니다. (NodePort의 포트 구조는 3장에서 Service와 함께 자세히 다룹니다.)

```text
# 개념 참고용 — 공용 환경에서는 실행하지 않음
kubectl expose pod pod-edu01 --type=NodePort --name=pod-edu01-svc
kubectl get svc pod-edu01-svc
# NAME             TYPE       CLUSTER-IP    EXTERNAL-IP   PORT(S)        AGE
# pod-edu01-svc    NodePort   10.111.13.3   <none>        80:30770/TCP   8s
#
# 80:30770의 의미: 모든 노드의 30770 포트(환경마다 다름)로 들어온 요청이 Pod의 80 포트로 전달됨.
# 브라우저에서 http://<노드IP>:30770 으로 접속하면 Pod의 호스트네임-IP가 보임.
```

## 5. 꼭 알아야 할 kubectl 명령 6가지

Pod를 다루는 기본기이자, 이후 모든 리소스에 똑같이 적용되는 패턴입니다.

```text
# 1) 생성/수정
k apply -f pod-edu.yaml

# 2) 목록 보기
k get pod

# 3) 상세 정보를 YAML로 보기 (현재 상태 포함)
k get pod pod-edu01 -oyaml

# 4) 상세 설명 + 이벤트 로그 보기 (문제 생기면 제일 먼저 볼 것!)
k describe pod pod-edu01

# 5) 컨테이너의 출력(로그) 보기 (print 디버깅의 그 로그)
k logs pod/pod-edu01

# 6) 컨테이너 안에 들어가기 (SSH처럼, 대화형 터미널이 있을 때)
k exec pod-edu01 -it -- sh

# 삭제
k delete pod pod-edu01
```

> **트러블슈팅 공식**: Pod가 이상하면 ① `describe`로 이벤트 확인 → ② `logs`로 앱 출력 확인
> → ③ `exec`로 들어가서 직접 확인. 이 순서만 기억해도 웬만한 문제는 원인을 찾습니다.
> 바로 아래 6절에서 이 공식을 실제로 써 봅니다.

## 6. Label — 리소스에 붙이는 꼬리표

**레이블(Label)** 은 리소스에 붙이는 `key=value` 꼬리표입니다. 시스템 동작에 직접적인 의미는 없지만,
"이 꼬리표가 붙은 것들만 골라줘"라는 **선택(select)** 에 쓰입니다. 앞으로 배울 Service, Deployment가
전부 레이블로 Pod를 찾아내기 때문에 매우 중요합니다.

> **Python 비유**: 객체마다 붙은 태그로 필터링하는 것과 같습니다.
> `[p for p in pods if p.labels.get("app") == "edu01-web"]`

```bash
# 레이블까지 같이 조회
k get pod --show-labels
```

```
NAME        READY   STATUS    RESTARTS   AGE     LABELS
pod-edu01   1/1     Running   0          3d17h   app=edu01-web
```

```bash
# app이라는 key를 가진 Pod만 조회
k get pod -l app

# app=edu01-web 인 것만 조회
k get pod -l app=edu01-web

# 레이블 추가
k label pod pod-edu01 env=dev

# 레이블 수정 (이미 있는 key는 --overwrite 필요)
k label pod pod-edu01 env=prod --overwrite
```

## 7. 실습 ② — 의도적 오류: 스케줄링 실패 체험 (nodeSelector)

실무에서 아주 흔한 사고 중 하나가 "Pod가 `Pending`에서 멈춰 있어요"입니다.
원인 중 하나가 **존재하지 않는 노드 레이블을 요구하는 nodeSelector**입니다.
(이 실습에서는 실제 노드에 레이블을 붙이지 않습니다 — 노드 설정은 절대 바꾸지 않습니다.
클러스터에 애초에 없는 레이블을 요구해서 실패를 재현합니다.)

([examples/01-pod/pod-edu-nodeselector.yaml](../examples/01-pod/pod-edu-nodeselector.yaml))

```yaml
spec:
  nodeSelector:         # 이 레이블이 붙은 노드에만 스케줄
    gpu: "true"          # 클러스터 어디에도 없는 레이블 (의도적 오류)
  containers:
  - name: web
    ...
```

### 7-1. 오류 재현

```bash
k delete pod pod-edu01 --ignore-not-found
k apply -f examples/01-pod/pod-edu-nodeselector.yaml
k wait pod/pod-edu01 --for=condition=PodScheduled=false --timeout=45s
k get pod pod-edu01
```

```
NAME        READY   STATUS    RESTARTS   AGE
pod-edu01   0/1     Pending   0          2s
```

### 7-2. 관찰 (힌트)

`STATUS`가 `Running`이 아니라 `Pending`에서 멈춰 있습니다. 5절의 트러블슈팅 공식대로
`describe`부터 봅니다.

```bash
k describe pod pod-edu01 | grep -A5 "Events:"
```

```
Events:
  Type     Reason            From               Message
  ----     ------            ----               -------
  Warning  FailedScheduling  default-scheduler  0/3 nodes are available: 3 node(s) didn't match Pod's node affinity/selector.
```

→ "didn't match Pod's node affinity/selector"가 보이면, `nodeSelector`(혹은 `affinity`)가 요구하는
레이블을 가진 노드가 없다는 뜻입니다. 이때 할 일은 노드에 없는 레이블을 억지로 붙이는 게 아니라
(이건 운영 중인 클러스터를 건드리는 위험한 작업입니다), **YAML의 요구 조건이 실제 클러스터 구성과
맞는지** 먼저 확인하는 것입니다.

### 7-3. 복구

<details><summary>조치하기 전, 원인과 수정할 대상을 먼저 설명해 보세요. 복구 방법 펼치기</summary>

이 실습에서는 nodeSelector 조건 자체가 잘못 설정된 것이므로, nodeSelector 없는 원래 정의로
되돌립니다.

```bash
k delete pod pod-edu01 --ignore-not-found
k apply -f examples/01-pod/pod-edu.yaml
```

</details>

### 7-4. 기능 검증

```bash
k wait --for=condition=Ready pod/pod-edu01 --timeout=60s
k get pod pod-edu01
k exec pod-edu01 -- wget -qO- http://127.0.0.1/
```

```
NAME        READY   STATUS    RESTARTS   AGE
pod-edu01   1/1     Running   0          5s
pod-edu01-10.244.1.24
```

`Running`으로 복구되고, 응답도 다시 정상적으로 돌아오면 복구 완료입니다.

## 8. 실습 정리 (청소)

```bash
k delete -f examples/01-pod/pod-edu.yaml --ignore-not-found
k delete -f examples/01-pod/pod-edu-nodeselector.yaml --ignore-not-found
```

## 확인 문제

1. Pod가 죽고 다시 만들어지면 IP가 바뀐다. 호스트네임도 항상 같이 바뀔까?
2. Pod 안의 컨테이너가 2개면, 두 컨테이너의 IP는 같을까 다를까?
3. `nodeSelector`가 가리키는 레이블을 가진 노드가 클러스터에 하나도 없으면 Pod는 어떤 상태가 되는가?

<details><summary>정답 보기</summary>

1. 아니다. 호스트네임은 보통 Pod 이름이므로, 똑같은 이름으로 다시 만들면 호스트네임은 그대로다. Deployment처럼 매번 새 이름(랜덤 해시)으로 Pod를 찍어낼 때만 호스트네임도 매번 바뀐다. IP는 재생성될 때마다 거의 항상 바뀐다.
2. 같다. Pod 안의 컨테이너들은 네트워크 네임스페이스를 공유한다 (같은 IP, 같은 포트 공간)
3. `Pending`. `describe pod`의 Events에 `FailedScheduling`과 `didn't match Pod's node affinity/selector`가 찍힌다.
</details>

---

다음 장: [02. Deployment — Pod를 관리해 주는 관리자](02-deployment.md)
