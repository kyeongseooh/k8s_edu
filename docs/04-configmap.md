# 04. ConfigMap — 설정을 코드와 분리하기

## 1. 개념

Python 프로젝트에서 설정을 코드에 하드코딩하지 않고 `config.json`이나 환경변수로 빼 본 적이 있을 겁니다.

```python
import os
DB_HOST = os.environ.get("DB_HOST", "localhost")   # 환경마다 다른 값
```

이렇게 해 두면 같은 코드를 개발/운영 환경에서 설정만 바꿔 쓸 수 있죠.
**ConfigMap(컨피그맵)** 은 쿠버네티스에서 이 "설정 묶음"을 담당하는 리소스입니다.

- 기밀이 **아닌** 설정 데이터를 `key: value` 형태로 저장 (비밀번호는 5장 Secret에)
- 저장한 값을 Pod에 **환경변수**로 주입하거나 **파일로 마운트**할 수 있음
- 같은 컨테이너 이미지를 환경(개발/운영)마다 다른 설정으로 실행 가능
- 크기 제한: 1MiB

```
[ConfigMap: env=dev, user_name=...]  ──환경변수 또는 파일──▶  [Pod의 컨테이너]
```

## 2. 실습 준비

00장에서 준비된 `$NS`, `k()`를 그대로 씁니다. 네임스페이스를 새로 만들거나 지우지 않습니다.

## 3. ConfigMap 만들기

### 방법 1: 명령어로

```text
# 리터럴(직접 입력) 값으로
k create configmap <이름> --from-literal=username=demo-user

# 파일 하나로 (key는 파일명, value는 파일 내용)
k create configmap <이름> --from-file=xxx.txt

# 디렉토리 통째로 (각 파일이 key가 됨)
k create configmap <이름> --from-file=/configdir/

# 혼합도 가능
k create configmap <이름> --from-file=myfile=xxx.txt --from-literal=username=demo-user
```

### 방법 2: YAML로

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cm-edu04
data:
  username: "demo-user"
  service.email.mysmtp: |      # '|' 는 여러 줄 문자열 (줄바꿈 유지)
    host: 10.0.0.50
    port: 1025
    from: demo-user@example.com
```

key 하나에 짧은 값도, 설정 파일 전체 같은 긴 텍스트도 넣을 수 있습니다. 이번 실습은 명령어 방식으로
ConfigMap을 만듭니다(파일 내용까지 함께 넣어 보기 위해서입니다).

## 4. 실습 ① — 정상: ConfigMap을 Pod에 주입하기

### 4-1. 준비: ConfigMap 생성

실습용 설정 파일과 ConfigMap을 만듭니다. (임시 파일은 저장소 바깥의 `/tmp`에 만들어 작업 폴더를
더럽히지 않습니다.)

```bash
CFGDIR=$(mktemp -d)
cat > "$CFGDIR/config.json" <<'EOF'
{
  "app_name": "My Application",
  "server": { "host": "0.0.0.0", "port": 8080 },
  "debug_mode": false,
  "logging": { "log_level": "info", "log_file": "/var/log/myapp.log" }
}
EOF

k create configmap cm-edu04 --from-file="$CFGDIR/" --from-literal=username=demo-user

# 내용 확인
k describe configmap cm-edu04
```

이제 `cm-edu04`에는 `config.json`(파일 내용)과 `username`(리터럴), 두 개의 key가 들어 있습니다.

### 4-2. 방법 ① 특정 key 하나만 환경변수로

([examples/04-configmap/pod-env-single.yaml](../examples/04-configmap/pod-env-single.yaml))

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-reader
spec:
  containers:
  - name: reader
    image: nginx:1.27-alpine
    env:
    - name: USERNAME            # 컨테이너에 보일 환경변수 이름
      valueFrom:
        configMapKeyRef:
          name: cm-edu04        # 어느 ConfigMap에서
          key: username          # 어느 key를 가져올까
    command: ["sleep", "3600"]  # 1시간 동안 대기 (실습용으로 살려두기)
    imagePullPolicy: IfNotPresent
  restartPolicy: Always
```

```bash
k apply -f examples/04-configmap/pod-env-single.yaml
k wait --for=condition=Ready pod/config-reader --timeout=60s
k exec config-reader -- sh -c "env | grep USER"
```

```
USERNAME=demo-user
```

### 4-3. 방법 ② ConfigMap 전체를 환경변수로

key가 많을 때 일일이 나열하는 대신 `envFrom`으로 통째로 넣습니다.
([examples/04-configmap/pod-env-all.yaml](../examples/04-configmap/pod-env-all.yaml))

```yaml
    envFrom:                    # env 대신 envFrom
    - configMapRef:
        name: cm-edu04          # 모든 key가 환경변수로 들어감
```

```bash
k delete pod config-reader --ignore-not-found
k apply -f examples/04-configmap/pod-env-all.yaml
k wait --for=condition=Ready pod/config-reader --timeout=60s
k exec config-reader -- sh -c "env | grep -E 'username|config.json'"
```

```
username=demo-user
config.json={ "app_name": "My Application", ... }    ← 파일 내용도 환경변수가 됨
```

### 4-4. 방법 ③ 특정 key만 골라서 파일(볼륨)로 마운트

설정 "파일"을 읽는 앱이라면 환경변수보다 파일 마운트가 자연스럽습니다.
([examples/04-configmap/pod-volume-items.yaml](../examples/04-configmap/pod-volume-items.yaml))

```yaml
  volumes:
    - name: config-volume
      configMap:
        name: cm-edu04
        items:                      # 이 목록에 있는 key만 마운트
          - key: config.json
            path: config.json       # 마운트될 파일명 (바꿀 수도 있음)
```

```bash
k delete pod config-reader --ignore-not-found
k apply -f examples/04-configmap/pod-volume-items.yaml
k wait --for=condition=Ready pod/config-reader --timeout=60s
k exec config-reader -- ls /etc/config/
k exec config-reader -- cat /etc/config/config.json
```

```
config.json          ← username은 없음 (items로 config.json만 지정했기 때문)
{ "app_name": "My Application", ... }
```

(전체 key를 마운트하고 싶다면 `items`를 빼면 됩니다 — [examples/04-configmap/pod-volume.yaml](../examples/04-configmap/pod-volume.yaml) 참고)

## 5. 실습 ② — 의도적 오류: 존재하지 않는 key 참조

ConfigMap 연동에서 실무적으로 가장 많이 겪는 실수는 **key 이름 오타**입니다.
([examples/04-configmap/pod-env-single-broken.yaml](../examples/04-configmap/pod-env-single-broken.yaml))

```yaml
    env:
    - name: USERNAME
      valueFrom:
        configMapKeyRef:
          name: cm-edu04
          key: usernam           # 오타! 실제 key는 username (의도적 오류)
```

### 5-1. 오류 재현

```bash
k delete pod config-reader --ignore-not-found
k apply -f examples/04-configmap/pod-env-single-broken.yaml
for i in $(seq 1 20); do
  reason=$(k get pod config-reader -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null)
  [ "$reason" = "CreateContainerConfigError" ] && break
  sleep 2
done
k get pod config-reader
```

```
NAME             READY   STATUS                       RESTARTS   AGE
config-reader    0/1     CreateContainerConfigError    0          5s
```

### 5-2. 관찰 (힌트)

```bash
k describe pod config-reader | grep -A5 "Events:"
```

```
Events:
  Type     Reason  From     Message
  ----     ------  ----     -------
  Warning  Failed  kubelet  Error: couldn't find key usernam in ConfigMap default/cm-edu04
```

→ `CreateContainerConfigError` + "couldn't find key ..." 메시지가 보이면, 참조하는 ConfigMap/Secret의
key 이름이 실제와 다르다는 뜻입니다. `k get configmap cm-edu04 -oyaml`로 실제 key 목록을 확인하고
비교하면 바로 원인을 찾을 수 있습니다.

### 5-3. 복구

<details><summary>조치하기 전, 원인과 수정할 대상을 먼저 설명해 보세요. 복구 방법 펼치기</summary>

```bash
k delete pod config-reader --ignore-not-found
k apply -f examples/04-configmap/pod-env-single.yaml
```

</details>

### 5-4. 기능 검증

```bash
k wait --for=condition=Ready pod/config-reader --timeout=60s
k get pod config-reader
k exec config-reader -- sh -c "env | grep USER"
```

```
NAME             READY   STATUS    RESTARTS   AGE
config-reader    1/1     Running   0          5s
USERNAME=demo-user
```

`Running`으로 복구되고 환경변수도 정상적으로 보이면 복구 완료입니다.

## 6. 알아두면 좋은 것

- **환경변수 주입은 Pod 시작 시점에 고정**됩니다. ConfigMap을 나중에 수정해도 이미 떠 있는 Pod의
  환경변수는 안 바뀝니다 (Pod 재시작 필요). 볼륨 마운트 방식은 시간이 지나면 파일이 갱신됩니다.
- ConfigMap은 **같은 네임스페이스**의 Pod에서만 참조할 수 있습니다.

## 7. 실습 정리

```bash
k delete pod config-reader --ignore-not-found
k delete configmap cm-edu04 --ignore-not-found
rm -rf "$CFGDIR"
```

## 확인 문제

1. ConfigMap에 DB 비밀번호를 넣으면 안 되는 이유는? 그럼 어디에 넣어야 하나?
2. ConfigMap을 Pod에 주입하는 두 가지 큰 방식은?
3. `configMapKeyRef`에서 존재하지 않는 key를 참조하면 Pod는 어떤 상태가 되는가?

<details><summary>정답 보기</summary>

1. ConfigMap은 평문 저장이라 조회 권한만 있으면 다 보인다. 민감 정보는 Secret(5장)에 넣는다.
2. 환경변수 주입(env/envFrom)과 파일 마운트(volume)
3. `CreateContainerConfigError`. `describe pod`의 Events에 "couldn't find key ..." 메시지가 남는다.
</details>

---

다음 장: [05. Secret — 민감한 값 관리하기](05-secret.md)
