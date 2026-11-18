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

## 2. ConfigMap 만들기

### 방법 1: 명령어로

```bash
# 리터럴(직접 입력) 값으로
kubectl create configmap <이름> --from-literal=username=kyeongseo.oh

# 파일 하나로 (key는 파일명, value는 파일 내용)
kubectl create configmap <이름> --from-file=xxx.txt

# 파일인데 key 이름을 직접 지정
kubectl create configmap <이름> --from-file=myfile=xxx.txt

# 디렉토리 통째로 (각 파일이 key가 됨)
kubectl create configmap <이름> --from-file=/configdir/

# 혼합도 가능
kubectl create configmap <이름> --from-file=myfile=xxx.txt --from-literal=username=kyeongseo.oh
```

### 방법 2: YAML로

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-edu
data:
  env: "dev"
  user_name: "kyeongseo.oh"
  service.email.mysmtp: |       # '|' 는 여러 줄 문자열 (줄바꿈 유지)
    host: 10.0.1.118
    port: 1025
    from: kyeongseo.oh@data-dynamics.io
```

key 하나에 짧은 값도, 설정 파일 전체 같은 긴 텍스트도 넣을 수 있습니다.

## 3. 실습 — ConfigMap을 Pod에 주입하는 4가지 방법

### 준비: ConfigMap 생성

실습용 설정 파일과 ConfigMap을 만듭니다.

```bash
mkdir -p configdir
cat > configdir/config.json <<'EOF'
{
  "app_name": "My Application",
  "server": { "host": "0.0.0.0", "port": 8080 },
  "debug_mode": false,
  "logging": { "log_level": "info", "log_file": "/var/log/myapp.log" }
}
EOF

kubectl create configmap edu-config --from-file=./configdir/ --from-literal=username=kyeongseo.oh

# 내용 확인
kubectl describe configmap edu-config
```

이제 `edu-config`에는 `config.json`(파일 내용)과 `username`(리터럴), 두 개의 key가 들어 있습니다.

### 방법 ① 특정 key 하나만 환경변수로

([examples/04-configmap/pod-env-single.yaml](../examples/04-configmap/pod-env-single.yaml))

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: busybox
spec:
  containers:
  - name: busybox
    image: busybox              # 디버깅용 초경량 리눅스 이미지
    env:
    - name: USERNAME            # 컨테이너에 보일 환경변수 이름
      valueFrom:
        configMapKeyRef:
          name: edu-config      # 어느 ConfigMap에서
          key: username         # 어느 key를 가져올까
    command: ["sleep", "3600"]  # 1시간 동안 대기 (실습용으로 살려두기)
    imagePullPolicy: IfNotPresent
  restartPolicy: Always
```

```bash
kubectl apply -f examples/04-configmap/pod-env-single.yaml
kubectl exec busybox -ti -- sh

/ # env | grep USER
USERNAME=kyeongseo.oh
/ # exit
```

### 방법 ② ConfigMap 전체를 환경변수로

key가 많을 때 일일이 나열하는 대신 `envFrom`으로 통째로 넣습니다.
([examples/04-configmap/pod-env-all.yaml](../examples/04-configmap/pod-env-all.yaml))

```yaml
spec:
  containers:
  - name: busybox
    image: busybox
    command: ["sleep", "3600"]
    envFrom:                    # env 대신 envFrom
    - configMapRef:
        name: edu-config        # 모든 key가 환경변수로 들어감
```

```bash
kubectl delete pod busybox
kubectl apply -f examples/04-configmap/pod-env-all.yaml
kubectl exec busybox -ti -- sh -c "env"
```

```
username=kyeongseo.oh
config.json={ "app_name": "My Application", ... }    ← 파일 내용도 환경변수가 됨
...
```

### 방법 ③ 파일(볼륨)로 마운트

설정 "파일"을 읽는 앱이라면 환경변수보다 파일 마운트가 자연스럽습니다.
([examples/04-configmap/pod-volume.yaml](../examples/04-configmap/pod-volume.yaml))

```yaml
spec:
  containers:
    - name: busybox
      image: busybox
      command: ["sleep", "3600"]
      volumeMounts:
        - name: config-volume       # 아래 volumes의 이름과 매칭
          mountPath: /etc/config    # 컨테이너 안에서 보일 경로
  volumes:
    - name: config-volume
      configMap:
        name: edu-config            # 이 ConfigMap의 key들이 파일이 됨
```

```bash
kubectl delete pod busybox
kubectl apply -f examples/04-configmap/pod-volume.yaml
kubectl exec busybox -ti -- sh

/ # ls /etc/config/
config.json  username
/ # cat /etc/config/username
kyeongseo.oh
/ # cat /etc/config/config.json
{ "app_name": "My Application", ... }
```

key 이름이 파일명, value가 파일 내용이 됩니다.

### 방법 ④ 특정 key만 골라서 마운트

([examples/04-configmap/pod-volume-items.yaml](../examples/04-configmap/pod-volume-items.yaml))

```yaml
  volumes:
    - name: config-volume
      configMap:
        name: edu-config
        items:                      # 이 목록에 있는 key만 마운트
          - key: config.json
            path: config.json       # 마운트될 파일명 (바꿀 수도 있음)
```

```bash
/ # ls /etc/config/
config.json          ← username은 없음
```

## 4. 알아두면 좋은 것

- **환경변수 주입은 Pod 시작 시점에 고정**됩니다. ConfigMap을 나중에 수정해도 이미 떠 있는 Pod의
  환경변수는 안 바뀝니다 (Pod 재시작 필요). 볼륨 마운트 방식은 시간이 지나면 파일이 갱신됩니다.
- ConfigMap은 **같은 네임스페이스**의 Pod에서만 참조할 수 있습니다.

## 5. 실습 정리

```bash
kubectl delete pod busybox
kubectl delete configmap edu-config
```

## 확인 문제

1. ConfigMap에 DB 비밀번호를 넣으면 안 되는 이유는? 그럼 어디에 넣어야 하나?
2. ConfigMap을 Pod에 주입하는 두 가지 큰 방식은?
3. `--from-file=/configdir/` 로 만들면 key는 무엇이 되는가?

<details><summary>정답 보기</summary>

1. ConfigMap은 평문 저장이라 조회 권한만 있으면 다 보인다. 민감 정보는 Secret(5장)에 넣는다.
2. 환경변수 주입(env/envFrom)과 파일 마운트(volume)
3. 디렉토리 안의 각 파일명이 key, 파일 내용이 value가 된다.
</details>

---

다음 장: [05. Secret — 민감한 값 관리하기](05-secret.md)
