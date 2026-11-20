# 07. StatefulSet — 이름과 데이터가 유지되어야 하는 앱

## 0. 이 장의 전제

00장에서 설정한 `EDU_CONTEXT`, `NS`, `k()`를 그대로 씁니다. 이 장은 **PV/PVC를 쓰지 않습니다.**
StatefulSet의 핵심인 "고정된 이름"을 **emptyDir**로 체험하고, emptyDir이 실제 PVC(6장)와
무엇이 다른지 직접 비교합니다. 특정 노드나 호스트를 지정하지 않으므로 스케줄러가 알아서 배치합니다.

```bash
k auth can-i create statefulsets.apps
```

## 1. 개념

Deployment는 Pod들을 "모두 똑같은 일회용"으로 취급합니다. 웹 서버처럼 어느 Pod가 응답해도
상관없는(**무상태, stateless**) 앱에는 완벽하지만, DB처럼 각자 **자기 데이터와 정체성**을 가져야 하는
(**유상태, stateful**) 앱에는 맞지 않습니다.

**StatefulSet(스테이트풀셋, 줄여서 sts)** 은 Pod의 **상태를 유지해 주는** 컨트롤러입니다.

- **Pod 이름이 고정**: `ch07-web-0`, `ch07-web-1`, `ch07-web-2` 처럼 번호가 붙고, 재시작해도 같은 이름 유지
- **순서 보장**: 0번부터 차례로 생성(0번이 Ready 돼야 1번 시작), 역순으로 종료
- **Pod마다 전용 볼륨 틀**: `volumeClaimTemplates`로 Pod별 PVC를 자동 생성할 수 있음 (이 장은 사용하지 않고, 6장에서 다룬 실제 PVC와 이름만 비교)

> **비유**: Deployment의 Pod들은 "교대 근무 아르바이트"(아무나 대체 가능),
> StatefulSet의 Pod들은 "각자 자기 사번(이름)이 있는 정직원"입니다.
> MySQL 클러스터에서 "0번이 프라이머리, 1·2번이 레플리카" 같은 역할 구분이 가능해집니다.

### Deployment와 비교해 보기

Deployment의 Pod 이름은 랜덤 해시가 붙고, 재시작하면 바뀝니다.

```
edu-deployment-6c7cbd7b6-s2jgm    ← 재시작하면 뒷부분이 바뀜
```

StatefulSet의 Pod는 `-0`, `-1`, `-2` 번호가 붙고 유지됩니다.

```
ch07-web-0              ← 재시작해도 ch07-web-0
```

중요한 건 "이름"만 유지된다는 것이고, **"같은 이름 = 같은 Pod"는 아닙니다.** Pod가 재생성되면
이름은 같아도 내부적으로는 완전히 새 객체(새 `UID`)입니다. 이 장의 실습은 이 차이를 직접 봅니다.

## 2. YAML 뜯어보기

nginx 3대를 각자 "전용 디렉토리"(emptyDir)와 함께 띄우는 예시입니다.
([examples/07-statefulset/sts-web.yaml](../examples/07-statefulset/sts-web.yaml))

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ch07-web
spec:
  serviceName: ch07-web        # ★ sts 전용: 연결할 headless Service 이름 (8장에서 설명)
  replicas: 3
  selector:
    matchLabels:
      app: ch07-web            # template의 레이블과 반드시 일치해야 함
  template:
    metadata:
      labels:
        app: ch07-web
    spec:
      terminationGracePeriodSeconds: 10
      containers:
      - name: nginx
        image: nginx:1.27-alpine
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 80
          name: web
        volumeMounts:
        - name: www
          mountPath: /usr/share/nginx/html
      volumes:
      - name: www
        emptyDir: {}            # ★ PVC가 아니라 emptyDir — Pod가 다시 생기면 이 안의 내용은 사라짐
---
apiVersion: v1
kind: Service
metadata:
  name: ch07-web
  labels:
    app: ch07-web
spec:
  clusterIP: None              # ★ headless 서비스 (8장)
  selector:
    app: ch07-web
  ports:
  - port: 80
    name: web
```

Deployment와 다른 포인트 2가지만 기억하세요.

1. `serviceName` + headless Service가 **필수** — Pod 하나하나에 고정 DNS 이름을 주기 위해 (8장)
2. `selector.matchLabels` = `template.metadata.labels` 가 반드시 일치해야 함 (Deployment·DaemonSet도 동일한 규칙)

## 3. 실습 — 정상 기준: 이름과 UID 관찰

```bash
k apply -f examples/07-statefulset/sts-web.yaml
k rollout status statefulset/ch07-web --timeout=120s
k get pod -l app=ch07-web
```

```
NAME         READY   STATUS    RESTARTS   AGE
ch07-web-0   1/1     Running   0          54s
ch07-web-1   1/1     Running   0          40s
ch07-web-2   1/1     Running   0          26s
```

이름이 `ch07-web-0`, `ch07-web-1`, `ch07-web-2` 로 **순서대로** 생성됩니다 (`AGE`가 0→1→2번
순으로 짧아지는 것이 "0번이 Ready 돼야 1번이 시작된다"는 순서 보장의 증거입니다).

```bash
# "이름"이 아니라 "이 객체가 맞는지"를 구분하는 고유 식별자: UID
k get pod ch07-web-0 -o jsonpath='{.metadata.uid}{"\n"}'
```

```
3f1e2a9c-....
```

이 UID를 기억해 둡니다. 아래에서 Pod를 지웠다가 다시 만든 뒤 **이름은 같지만 UID는 달라지는지**
확인합니다.

## 4. 오류 주입 — Pod 삭제로 emptyDir 데이터 날리기

```bash
# web-0에 파일 기록 + HTTP로도 응답되는지 확인
k exec ch07-web-0 -- sh -c "echo 'ch07-web-0의 데이터' > /usr/share/nginx/html/test.txt"
k exec ch07-web-0 -- wget -qO- http://localhost/test.txt
```

```
ch07-web-0의 데이터
```

```bash
# web-0을 "일부러" 삭제 (장애 상황 가정: 노드 장애, OOM 등으로 Pod가 사라졌다고 가정)
OLD_UID=$(k get pod ch07-web-0 -o jsonpath='{.metadata.uid}')
k delete pod ch07-web-0
k wait --for=condition=Ready pod/ch07-web-0 --timeout=60s
NEW_UID=$(k get pod ch07-web-0 -o jsonpath='{.metadata.uid}')

echo "이름은 동일: ch07-web-0"
echo "OLD_UID=$OLD_UID"
echo "NEW_UID=$NEW_UID"
if [[ "$OLD_UID" != "$NEW_UID" ]]; then
  echo "→ 다른 객체(UID 변경)로 재생성됨"
else
  echo "→ 예상과 다름: UID가 바뀌지 않았다 (확인 필요)"
fi

# 예상된 실패: emptyDir은 Pod와 함께 사라졌으므로 파일이 없어야 정상
k exec ch07-web-0 -- wget -qO- http://localhost/test.txt || true
k exec ch07-web-0 -- cat /usr/share/nginx/html/test.txt || true
```

```
이름은 동일: ch07-web-0
OLD_UID=3f1e2a9c-....
NEW_UID=7b84d110-....
→ 다른 객체(UID 변경)로 재생성됨
cat: can't open '/usr/share/nginx/html/test.txt': No such file or directory
```

**관찰**: `ch07-web-0`이라는 **이름**은 StatefulSet이 그대로 지켜 줬지만, `UID`는 바뀌었고
(완전히 새로운 Pod 객체) `test.txt`도 사라졌습니다. emptyDir은 "이 Pod 인스턴스가 살아있는 동안만"
유지되는 저장소라서, Pod가 재생성되면 새 emptyDir로 다시 시작합니다.

## 5. 복구 — 파일을 다시 쓰고 HTTP로 기능 확인

<details><summary>힌트와 복구</summary>

이름이 같다고 데이터도 돌아오는 게 아니므로, **다시 써넣는 것**이 유일한 복구 방법입니다
(실제 운영에서는 이 지점에서 "그래서 PVC가 필요하다"는 결론에 도달합니다 — 6장 참고).

```bash
k exec ch07-web-0 -- sh -c "echo 'ch07-web-0의 데이터(복구됨)' > /usr/share/nginx/html/test.txt"
k exec ch07-web-0 -- wget -qO- http://localhost/test.txt
```

```
ch07-web-0의 데이터(복구됨)
```

HTTP 응답이 다시 정상으로 돌아오면 **기능은 복구된 것**입니다. 다만 이번에 쓴 데이터도
Pod가 또 재생성되면 똑같이 사라집니다 — emptyDir은 "기능 복구"는 가능해도 "데이터 보존"은
해 주지 않는다는 뜻입니다.
</details>

| | emptyDir (이 장) | 실제 PVC (6장) |
|---|---|---|
| Pod 재생성 후 이름 | 유지 | 유지 |
| Pod 재생성 후 UID | **변경** (새 객체) | **변경** (새 객체) |
| Pod 재생성 후 데이터 | **사라짐** | **유지됨** |
| 저장 위치 | Pod가 뜬 노드의 임시 공간 | 네트워크 스토리지(NFS 등)의 독립 공간 |

**결론**: StatefulSet이 보장하는 것은 "이름과 순서"뿐이며, Pod 자체의 정체성(UID)이나 데이터까지
지켜 주지는 않습니다. 데이터까지 유지하려면 `volumeClaimTemplates`로 **실제 PVC**를 Pod마다
붙여야 합니다 (문법은 6장의 PVC와 동일하고, StatefulSet이 `<이름>-<pod이름>` 규칙으로 자동
생성해 준다는 점만 다릅니다).

```yaml
# 참고용 — 이 장에서는 실제로 적용하지 않습니다.
volumeClaimTemplates:
- metadata:
    name: www
  spec:
    accessModes: ["ReadWriteOnce"]
    storageClassName: nfs-client
    resources:
      requests:
        storage: 1Gi
```

## 6. 그래서 언제 무엇을 쓰나?

| | Deployment | StatefulSet |
|---|---|---|
| Pod 이름 | 랜덤, 재시작 시 변경 | 번호 고정 (`-0`, `-1`...) |
| 볼륨 | 공유하거나 없음 | Pod별 전용 볼륨 틀 가능 (`volumeClaimTemplates`) |
| 생성 순서 | 동시에 | 순서대로 |
| 적합한 앱 | 웹 서버, API, 워커 | DB(MySQL, PostgreSQL), Kafka, ZooKeeper, Redis 등 |

**"Pod가 서로 구분되어야 하고, 각자 데이터를 가진다"** → StatefulSet(+실제 PVC). 그 외에는 Deployment.

> 롤링 업데이트/롤백은 2장의 Deployment와 같은 개념이 StatefulSet에도 그대로 적용됩니다
> (`kubectl set image`, `kubectl rollout undo` 등). 차이는 **교체 순서가 역순**(번호가 큰
> Pod부터)이라는 점뿐입니다.

## 7. 실습 정리

```bash
k delete -f examples/07-statefulset/sts-web.yaml --ignore-not-found
```

## 확인 문제

1. StatefulSet의 Pod `ch07-web-1`을 삭제하면 새 Pod의 이름은? UID는?
2. "이름이 같다"와 "같은 Pod다"는 같은 뜻인가?
3. emptyDir을 쓴 StatefulSet에서 Pod가 재생성되면 이름과 데이터 중 무엇이 유지되는가? 데이터까지 유지하려면 무엇을 써야 하는가?

<details><summary>정답 보기</summary>

1. 이름은 `ch07-web-1`로 동일하게 재생성되지만, UID는 매번 새로 발급된다 (다른 객체).
2. 아니다. 이름은 StatefulSet이 보장해 주는 규칙일 뿐이고, Pod 객체 자체는 재생성될 때마다 새 UID를 가진 완전히 새로운 객체다.
3. 이름만 유지되고 데이터는 사라진다. 데이터까지 유지하려면 `volumeClaimTemplates`로 Pod마다 실제 PVC를 붙여야 한다 (6장).
</details>

---

다음 장: [08. Headless Service — Pod 하나하나를 직접 찾아가기](08-headless-service.md)
