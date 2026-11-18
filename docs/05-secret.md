# 05. Secret — 비밀번호, 토큰 같은 민감한 값 관리하기

## 1. 개념

**Secret(시크릿)** 은 ConfigMap과 거의 같은데, **민감한 데이터 전용**입니다.

- 비밀번호, API 토큰, 인증서 키 같은 값을 저장
- 값은 **base64로 인코딩**되어 저장됨
- Pod에 주입하는 방법은 ConfigMap과 동일 (환경변수 / 파일 마운트)
- 최대 크기 1MB

| | ConfigMap | Secret |
|---|---|---|
| 용도 | 일반 설정 | 비밀번호, 토큰, 인증서 |
| 저장 형태 | 평문 | base64 인코딩 |

> **중요한 주의**: base64는 **암호화가 아니라 인코딩**입니다. Python으로 치면
> `base64.b64decode(...)` 한 줄로 원문이 나옵니다. 그런데 왜 Secret을 쓸까요?
> ① ConfigMap과 "민감/비민감"을 구분해서 권한(RBAC, 11장)을 다르게 걸 수 있고,
> ② etcd 저장 시 암호화(encryption at rest)를 켤 수 있고,
> ③ 로그·화면에 실수로 노출될 확률이 줄기 때문입니다.
> 어쨌든 "Secret 조회 권한 = 비밀번호 열람 권한"이라는 점은 꼭 기억하세요.

## 2. Secret 만들기 — 3가지 서브커맨드

`kubectl create secret`에는 용도별로 3가지 종류가 있습니다.

```
Available Commands:
  generic          일반 값 (파일, 디렉토리, 리터럴)
  docker-registry  프라이빗 Docker 레지스트리 로그인 정보
  tls              TLS 인증서/키
```

### generic — 가장 많이 씀

```bash
# 리터럴 값으로
kubectl create secret generic literal \
  --from-literal=env=prod --from-literal=username=kyeongseo.oh

# 파일로 (예: docker 설정 파일을 지정된 타입으로)
kubectl create secret generic docker-config-secret \
    --from-file=.dockerconfigjson=/root/.docker/config.json \
    --type=kubernetes.io/dockerconfigjson

# 사설 CA 인증서 파일을 Secret으로
kubectl create secret generic harbor-ca-cert \
  --from-file=ca.crt=/etc/docker/certs.d/ks4.dd.io/ca.crt
```

### docker-registry — 프라이빗 레지스트리에서 이미지 받을 때

회사 내부 레지스트리(예: Harbor)에서 이미지를 pull하려면 로그인 정보가 필요합니다.

```bash
kubectl create secret docker-registry docker \
  --docker-server=ks4.dd.io --docker-username=admin --docker-password=Harbor12345
```

이렇게 만든 Secret을 Pod의 `imagePullSecrets`에 지정하면 프라이빗 이미지를 받을 수 있습니다.

### tls — HTTPS 인증서

```bash
kubectl create secret tls my-tls --cert=server.crt --key=server.key
```

## 3. Secret의 빌트인 타입

| 타입 | 사용처 |
|--------|-----|
| `Opaque` (기본값) | 임의의 사용자 정의 데이터 |
| `kubernetes.io/service-account-token` | 서비스 어카운트 토큰 |
| `kubernetes.io/dockercfg` | 직렬화된 `~/.dockercfg` 파일 |
| `kubernetes.io/dockerconfigjson` | 직렬화된 `~/.docker/config.json` 파일 |
| `kubernetes.io/basic-auth` | 기본 인증 자격 증명 |
| `kubernetes.io/ssh-auth` | SSH 자격 증명 |
| `kubernetes.io/tls` | TLS 클라이언트/서버용 데이터 |
| `bootstrap.kubernetes.io/token` | 부트스트랩 토큰 |

처음에는 `Opaque`(generic으로 만들면 이 타입)만 기억해도 충분합니다.

## 4. 실습 — Secret을 Pod에 주입하기

주입 방법은 4장 ConfigMap과 완전히 평행합니다. `configMapKeyRef → secretKeyRef`,
`configMapRef → secretRef`, `configMap: → secret:` 으로 단어만 바뀝니다.

### 준비

```bash
kubectl create secret generic literal \
  --from-literal=env=prod --from-literal=username=kyeongseo.oh

# 저장된 모습 확인 — 값이 base64로 보임
kubectl get secret literal -oyaml
```

```yaml
data:
  env: cHJvZA==                # "prod"의 base64
  username: a3llb25nc2VvLm9o
```

```bash
# base64 디코딩해 보기
echo cHJvZA== | base64 -d
# prod
```

### 방법 ① 특정 key만 환경변수로

([examples/05-secret/pod-env-single.yaml](../examples/05-secret/pod-env-single.yaml))

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: busybox
spec:
  containers:
  - name: busybox
    image: busybox
    command: ["sleep", "3600"]
    env:
    - name: ENV
      valueFrom:
        secretKeyRef:          # ConfigMap 때의 configMapKeyRef와 동일 패턴
          name: literal
          key: env
    imagePullPolicy: IfNotPresent
  restartPolicy: Always
```

```bash
kubectl apply -f examples/05-secret/pod-env-single.yaml
kubectl exec busybox -ti -- sh -c "env | grep ENV"
# ENV=prod        ← 컨테이너 안에서는 디코딩된 원래 값으로 보임
```

### 방법 ② Secret 전체를 환경변수로

([examples/05-secret/pod-env-all.yaml](../examples/05-secret/pod-env-all.yaml))

```yaml
    envFrom:
      - secretRef:
          name: literal
```

```bash
kubectl delete pod busybox
kubectl apply -f examples/05-secret/pod-env-all.yaml
kubectl exec busybox -ti -- sh -c "env | grep -E 'env|username'"
# env=prod
# username=kyeongseo.oh
```

### 방법 ③ 파일로 마운트

([examples/05-secret/pod-volume.yaml](../examples/05-secret/pod-volume.yaml))

```yaml
    volumeMounts:
    - name: secret-volume
      readOnly: true                 # Secret은 읽기 전용 마운트가 기본 예의
      mountPath: /etc/secret-volume
  volumes:
  - name: secret-volume
    secret:
      secretName: literal
```

```bash
kubectl delete pod busybox
kubectl apply -f examples/05-secret/pod-volume.yaml
kubectl exec busybox -ti -- sh

/ # ls /etc/secret-volume/
env       username
/ # cat /etc/secret-volume/env
prod
```

### 방법 ④ 특정 key만 골라 마운트 + 파일명 변경

([examples/05-secret/pod-volume-items.yaml](../examples/05-secret/pod-volume-items.yaml))

```yaml
  volumes:
  - name: secret-volume
    secret:
      secretName: literal
      items:
      - key: env
        path: env.txt            # env 라는 key를 env.txt 라는 파일로
```

```bash
/ # ls /etc/secret-volume/
env.txt
/ # cat /etc/secret-volume/env.txt
prod
```

## 5. 실습 정리

```bash
kubectl delete pod busybox
kubectl delete secret literal
```

## 확인 문제

1. Secret의 base64 인코딩은 암호화인가?
2. 프라이빗 Docker 레지스트리에서 이미지를 받기 위한 Secret 종류는?
3. ConfigMap의 `configMapKeyRef`에 대응하는 Secret의 필드명은?

<details><summary>정답 보기</summary>

1. 아니다. 누구나 한 줄로 디코딩할 수 있는 인코딩일 뿐이다. 보안은 접근 권한(RBAC)과 etcd 암호화로 보강해야 한다.
2. `kubectl create secret docker-registry` (타입: kubernetes.io/dockerconfigjson)
3. `secretKeyRef`
</details>

---

다음 장: [06. PV / PVC — Pod가 죽어도 데이터는 남게](06-pv-pvc.md)
