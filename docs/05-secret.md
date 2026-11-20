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

## 2. 실습 준비

00장에서 준비된 `$NS`, `k()`를 그대로 씁니다. 네임스페이스를 새로 만들거나 지우지 않습니다.

## 3. Secret 만들기 — 3가지 서브커맨드

`kubectl create secret`에는 용도별로 3가지 종류가 있습니다.

```text
Available Commands:
  generic          일반 값 (파일, 디렉토리, 리터럴)
  docker-registry  프라이빗 Docker 레지스트리 로그인 정보
  tls              TLS 인증서/키
```

### generic — 가장 많이 씀 (이번 실습에서 사용)

```text
# 리터럴 값으로
k create secret generic <이름> \
  --from-literal=env=prod --from-literal=username=demo-user

# 파일로 (예: docker 설정 파일을 지정된 타입으로)
k create secret generic docker-config-secret \
    --from-file=.dockerconfigjson=/root/.docker/config.json \
    --type=kubernetes.io/dockerconfigjson
```

### docker-registry — 프라이빗 레지스트리에서 이미지 받을 때 (개념)

```text
k create secret docker-registry docker \
  --docker-server=<레지스트리주소> --docker-username=admin --docker-password=<비밀번호>
```

이렇게 만든 Secret을 Pod의 `imagePullSecrets`에 지정하면 프라이빗 이미지를 받을 수 있습니다.

### tls — HTTPS 인증서 (개념)

```text
k create secret tls my-tls --cert=server.crt --key=server.key
```

## 4. Secret의 빌트인 타입

| 타입 | 사용처 |
|--------|-----|
| `Opaque` (기본값) | 임의의 사용자 정의 데이터 |
| `kubernetes.io/service-account-token` | 서비스 어카운트 토큰 |
| `kubernetes.io/dockerconfigjson` | 직렬화된 `~/.docker/config.json` 파일 |
| `kubernetes.io/basic-auth` | 기본 인증 자격 증명 |
| `kubernetes.io/ssh-auth` | SSH 자격 증명 |
| `kubernetes.io/tls` | TLS 클라이언트/서버용 데이터 |

처음에는 `Opaque`(generic으로 만들면 이 타입)만 기억해도 충분합니다.

## 5. 실습 ① — 정상: Secret을 Pod에 주입하기

주입 방법은 4장 ConfigMap과 완전히 평행합니다. `configMapKeyRef → secretKeyRef`,
`configMapRef → secretRef`, `configMap: → secret:` 으로 단어만 바뀝니다.

### 5-1. 준비

```bash
k create secret generic secret-edu05 \
  --from-literal=env=prod --from-literal=username=demo-user

# 저장된 모습 확인 — 값이 base64로 보임
k get secret secret-edu05 -oyaml
```

```yaml
data:
  env: cHJvZA==                # "prod"의 base64
  username: ZGVtby11c2Vy
```

```bash
# base64 디코딩해 보기
echo cHJvZA== | base64 -d; echo
```

```
prod
```

### 5-2. 방법 ① 특정 key만 환경변수로

([examples/05-secret/pod-env-single.yaml](../examples/05-secret/pod-env-single.yaml))

```yaml
    env:
    - name: ENV
      valueFrom:
        secretKeyRef:          # ConfigMap 때의 configMapKeyRef와 동일 패턴
          name: secret-edu05
          key: env
```

```bash
k apply -f examples/05-secret/pod-env-single.yaml
k wait --for=condition=Ready pod/secret-reader --timeout=60s
k exec secret-reader -- sh -c "env | grep ENV"
```

```
ENV=prod        ← 컨테이너 안에서는 디코딩된 원래 값으로 보임
```

### 5-3. 방법 ② Secret 전체를 환경변수로

([examples/05-secret/pod-env-all.yaml](../examples/05-secret/pod-env-all.yaml))

```yaml
    envFrom:
      - secretRef:
          name: secret-edu05
```

```bash
k delete pod secret-reader --ignore-not-found
k apply -f examples/05-secret/pod-env-all.yaml
k wait --for=condition=Ready pod/secret-reader --timeout=60s
k exec secret-reader -- sh -c "env | grep -E 'env=|username='"
```

```
env=prod
username=demo-user
```

### 5-4. 방법 ③ 파일로 마운트 + 특정 key만 골라 파일명 변경

([examples/05-secret/pod-volume-items.yaml](../examples/05-secret/pod-volume-items.yaml))

```yaml
    volumeMounts:
    - name: secret-volume
      readOnly: true                 # Secret은 읽기 전용 마운트가 기본 예의
      mountPath: /etc/secret-volume
  volumes:
  - name: secret-volume
    secret:
      secretName: secret-edu05
      items:
      - key: env
        path: env.txt            # env 라는 key를 env.txt 라는 파일로
```

```bash
k delete pod secret-reader --ignore-not-found
k apply -f examples/05-secret/pod-volume-items.yaml
k wait --for=condition=Ready pod/secret-reader --timeout=60s
k exec secret-reader -- ls /etc/secret-volume/
k exec secret-reader -- cat /etc/secret-volume/env.txt
```

```
env.txt
prod
```

**비교: 읽기 전용 마운트 확인** — Secret 볼륨은 `readOnly: true`로 마운트하는 것이 기본 예의입니다.
실제로 쓰기가 막혀 있는지 확인해 봅시다.

```bash
k exec secret-reader -- sh -c "echo hack > /etc/secret-volume/env.txt" \
  || echo "쓰기 거부됨 (예상된 동작 — 읽기 전용 마운트)"
```

```
쓰기 거부됨 (예상된 동작 — 읽기 전용 마운트)
```

(전체 key를 마운트하고 싶다면 `items`를 빼면 됩니다 — [examples/05-secret/pod-volume.yaml](../examples/05-secret/pod-volume.yaml) 참고)

## 6. 실습 ② — 의도적 오류: 존재하지 않는 key 참조

4장과 똑같은 패턴의 실수가 Secret에서도 그대로 일어납니다.
([examples/05-secret/pod-env-single-broken.yaml](../examples/05-secret/pod-env-single-broken.yaml))

```yaml
    env:
    - name: ENV
      valueFrom:
        secretKeyRef:
          name: secret-edu05
          key: env2              # 오타! 실제 key는 env (의도적 오류)
```

### 6-1. 오류 재현

```bash
k delete pod secret-reader --ignore-not-found
k apply -f examples/05-secret/pod-env-single-broken.yaml
for i in $(seq 1 20); do
  reason=$(k get pod secret-reader -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null)
  [ "$reason" = "CreateContainerConfigError" ] && break
  sleep 2
done
k get pod secret-reader
```

```
NAME             READY   STATUS                       RESTARTS   AGE
secret-reader    0/1     CreateContainerConfigError    0          5s
```

### 6-2. 관찰 (힌트)

```bash
k describe pod secret-reader | grep -A5 "Events:"
```

```
Events:
  Type     Reason  From     Message
  ----     ------  ----     -------
  Warning  Failed  kubelet  Error: couldn't find key env2 in Secret default/secret-edu05
```

ConfigMap과 완전히 같은 형태의 메시지입니다. `k get secret secret-edu05 -oyaml`로 실제 key
목록(`env`, `username`)을 확인하면 바로 오타를 잡을 수 있습니다.

### 6-3. 복구

<details><summary>조치하기 전, 원인과 수정할 대상을 먼저 설명해 보세요. 복구 방법 펼치기</summary>

```bash
k delete pod secret-reader --ignore-not-found
k apply -f examples/05-secret/pod-env-single.yaml
```

</details>

### 6-4. 기능 검증

```bash
k wait --for=condition=Ready pod/secret-reader --timeout=60s
k get pod secret-reader
k exec secret-reader -- sh -c "env | grep ENV"
```

```
NAME             READY   STATUS    RESTARTS   AGE
secret-reader    1/1     Running   0          5s
ENV=prod
```

`Running`으로 복구되고 디코딩된 값이 정상적으로 보이면 복구 완료입니다.

## 7. 실습 정리

```bash
k delete pod secret-reader --ignore-not-found
k delete secret secret-edu05 --ignore-not-found
```

## 확인 문제

1. Secret의 base64 인코딩은 암호화인가?
2. ConfigMap의 `configMapKeyRef`에 대응하는 Secret의 필드명은?
3. Secret을 볼륨으로 마운트할 때 `readOnly: true`를 쓰는 이유는?

<details><summary>정답 보기</summary>

1. 아니다. 누구나 한 줄로 디코딩할 수 있는 인코딩일 뿐이다. 보안은 접근 권한(RBAC)과 etcd 암호화로 보강해야 한다.
2. `secretKeyRef`
3. 컨테이너가 민감한 값을 실수로(혹은 악의적으로) 덮어쓰거나 지우는 것을 막기 위해서다.
</details>

---

다음 장: [06. PV / PVC — Pod가 죽어도 데이터는 남게](06-pv-pvc.md)
