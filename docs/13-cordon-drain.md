# 13. Cordon / Drain — 서버 점검을 위해 노드를 안전하게 비우기

> 이 장도 **사고 대응 실습** 형식입니다. 다만 이번 장은 **실제 cordon/drain/evict나 노드
> 자체를 건드리지 않습니다.** 대신 학습용 Deployment + PodDisruptionBudget(PDB)을 가지고,
> "자발적 축출(voluntary disruption)이 왜 막히는지"를 `disruptionsAllowed` 숫자로 직접
> 관찰하고 안전하게 풀어봅니다. 실제 노드 점검 절차는 마지막에 **텍스트로만** 비교합니다.
> 0장에서 배정받은 개인 네임스페이스(`$NS`)를 그대로 쓰고, 네임스페이스는 만들거나
> 지우지 않습니다.

## 1. 개념

노드(서버)의 OS를 업데이트하거나 하드웨어를 점검해야 할 때, 그 위에서 돌고 있는 Pod들을
어떻게 해야 할까요? 그냥 서버를 꺼 버리면 서비스 장애가 납니다. 쿠버네티스는 이를 위한
두 단계 도구를 제공합니다.

### cordon — 출입 금지 팻말

- 해당 노드를 **스케줄링 대상에서 제외** — 새 Pod가 더 이상 배정되지 않음
- **기존에 돌던 Pod는 그대로** 둠

### drain — 배수(비우기)

- cordon(출입 금지) + 기존 Pod들에 **Eviction API**를 호출해서 다른 노드로 옮김
- 쫓겨난 Pod는 Deployment/StatefulSet 같은 컨트롤러가 다른 노드에 재생성해 줌

> **비유**: 식당 한 구역을 수리한다면 — cordon은 "신규 손님은 이 구역에 앉히지 마"
> (기존 손님은 식사 계속), drain은 "기존 손님도 모두 다른 구역으로 옮겨 드리고 구역을 비워"입니다.

### PodDisruptionBudget(PDB) — "최소 몇 개는 항상 살아 있어야 한다"

drain이 Pod를 쫓아낼 때 쓰는 **Eviction API**는 막무가내로 다 쫓아내지 않습니다. PDB가
있으면, "지금 당장 몇 개까지 안전하게 쫓아낼 수 있는지"를 계산해서 그 수를 넘으면 **축출
자체를 거부**합니다. 그 계산 결과가 `kubectl get pdb`의 `disruptionsAllowed` 컬럼입니다.

> **중요한 구분**: PDB는 **자발적 축출(Eviction API) 에만** 적용됩니다. `kubectl delete pod`로
> 직접 지우거나, 레플리카 수를 줄이는 스케일 다운은 PDB의 통제 대상이 아닙니다. (drain과
> descheduler가 대표적으로 Eviction API를 씁니다.)

## 2. 정상 상태 만들기 — Deployment + PDB

([examples/13-cordon-drain/pdb-lab.yaml](../examples/13-cordon-drain/pdb-lab.yaml))

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: catalog-web
spec:
  replicas: 4
  selector:
    matchLabels:
      app: catalog-web
  template:
    metadata:
      labels:
        app: catalog-web
    spec:
      containers:
      - name: catalog-web
        image: nginx:1.27-alpine
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 80
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: catalog-web-pdb
spec:
  minAvailable: 3        # 건강한 복제본 최소 3개를 유지
  selector:
    matchLabels:
      app: catalog-web
```

```bash
k apply -f examples/13-cordon-drain/pdb-lab.yaml
k rollout status deployment/catalog-web --timeout=90s
k wait pdb/catalog-web-pdb --for=jsonpath='{.status.disruptionsAllowed}'=1 --timeout=60s
```

정상 상태에서는 복제본 4개가 준비되어 있고, 이 PDB 기준으로 자발적 축출 1개가 가능합니다.

## 3. 장애 발생 — "이 노드 점검해도 될까요?" 미리 확인했더니...

운영팀 요청: "오늘 밤 노드 점검이 있는데, `catalog-web`이 영향받을지 미리 확인해 주세요."
비용 절감을 위해 누군가 복제본을 한 개 줄인 상황을 내 Deployment에서 재현합니다. 앱은 정상이어도 점검에 쓸 여유가 남아 있을까요?

```bash
k scale deployment catalog-web --replicas=3
k rollout status deployment/catalog-web --timeout=90s
k wait pdb/catalog-web-pdb --for=jsonpath='{.status.disruptionsAllowed}'=0 --timeout=60s
k get pdb catalog-web-pdb
```

```
NAME              MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
catalog-web-pdb   3               N/A                0                    1m
```

### 증거 / 질문

```bash
k get deploy catalog-web -o jsonpath='{.spec.replicas}{"\n"}'
# 3

k get pdb catalog-web-pdb -o jsonpath='{.spec.minAvailable}{"\n"}'
# 3

k get pdb catalog-web-pdb -o jsonpath='{.status.disruptionsAllowed}{"\n"}'
# 0
```

- `replicas`와 `minAvailable`이 똑같이 3입니다. "지금 떠 있는 3개 중 몇 개까지 비워도
  `minAvailable`을 지킬 수 있을까요?"
- `disruptionsAllowed`가 0이라는 건, 지금 당장 누군가 drain(또는 descheduler)으로 이
  Deployment의 Pod를 **단 1개도** 자발적으로 축출할 수 없다는 뜻입니다. 오늘 밤 이 노드에
  `catalog-web` Pod가 있다면 drain이 거기서 막혀 대기하게 됩니다.
- `minAvailable`을 낮추는 것과, `replicas`를 늘리는 것 — 어느 쪽이 "여유"를 만들면서도
  실제 서비스 용량을 줄이지 않는 방법일까요?

## 4. 복구 (막혔을 때만 펼쳐보세요)

<details><summary>안전한 해결 방법 보기</summary>

PDB의 `minAvailable`을 낮추는 건 "항상 떠 있어야 하는 최소 개수"를 줄이는 것이라, 서비스
안정성 기준 자체를 낮추는 셈입니다. 더 안전한 방법은 **여유 복제본을 늘려서** 간격을
만드는 것입니다.

```bash
k scale deployment catalog-web --replicas=4
k rollout status deployment/catalog-web --timeout=90s
k wait pdb/catalog-web-pdb --for=jsonpath='{.status.disruptionsAllowed}'=1 --timeout=60s
k get pdb catalog-web-pdb
```

```
NAME              MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
catalog-web-pdb   3               N/A                1                    2m
```

</details>

## 5. 성공 판정

```bash
ALLOWED=$(k get pdb catalog-web-pdb -o jsonpath='{.status.disruptionsAllowed}')
echo "disruptionsAllowed=$ALLOWED"
if [ "$ALLOWED" -ge 1 ]; then
  echo "PASS: 이 PDB에서 자발적 축출 1개를 허용"
else
  echo "FAIL: 여전히 0 — 아직 여유가 없음"
fi
```

`disruptionsAllowed >= 1`이면 성공입니다. 즉 `minAvailable=3`이라는 안정성 기준은 그대로
지키면서 이 앱의 점검 여유를 회복했습니다. **이 숫자가 drain 전체의 성공을 보장하지는 않습니다.** 다른 앱의 PDB, 대체 노드의 자원·배치 조건, 로컬 데이터도 따로 확인합니다.

## 6. 실무 절차 비교 (텍스트로만 — 실행하지 않음)

실제 운영에서 노드를 점검할 때는 다음 순서를 씁니다. **이 실습에서는 아래를 실행하지
않습니다** — 실제 노드와 클러스터 상태를 바꾸는 명령이기 때문입니다.

```text
1. kubectl cordon <노드>                              # 신규 스케줄링 금지
2. kubectl drain <노드> --ignore-daemonsets          # 정책이 허용하는 Pod를 Eviction API로 축출
     # ↳ 이때 PDB의 disruptionsAllowed가 0이면 drain은 그 Pod를 비우지 못하고 대기/재시도한다
3. (OS 패치, 재부팅, 하드웨어 점검 등)
4. kubectl uncordon <노드>                             # 스케줄링 복귀
```

- `--ignore-daemonsets`: DaemonSet Pod(9장)는 "노드당 1개"가 숙명이라 다른 노드로 옮길 수
  없으므로 무시하고 진행하라는 옵션. 거의 항상 필요합니다.
- `--delete-emptydir-data`: emptyDir 데이터가 소실되어도 되는지 소유자가 확인·승인한 특수한 경우의 옵션입니다. 기본 절차에 붙이지 않습니다.
- `disruptionsAllowed`는 **이 PDB가 허용하는 축출 수**의 현재 관측값입니다. 실무에서는 drain 전에 반드시 관련 PDB 상태를
  먼저 확인합니다.
- `uncordon`해도 쫓겨났던 Pod들이 자동으로 "돌아오지는" 않습니다. 이후 새로 생기는 Pod부터
  그 노드에 배정될 수 있게 되는 것입니다.

## 7. 정리

```bash
k delete pdb catalog-web-pdb
k delete deployment catalog-web
```

## 확인 문제

1. cordon과 drain의 차이 한 줄 요약은?
2. PDB는 어떤 종류의 Pod 제거(삭제)에 적용되는가? (힌트: 모든 삭제에 적용되지 않는다)
3. `disruptionsAllowed`가 0일 때 가장 안전한 해결 방법은 무엇이고, 왜 `minAvailable`을
   낮추는 것보다 나은가?

<details><summary>정답 보기</summary>

1. cordon은 "새 Pod만 금지"(기존 유지), drain은 "새 Pod 금지 + 기존 Pod도 Eviction API로
   다른 노드로 이동"
2. Eviction API를 통한 자발적 축출(voluntary disruption)에만 적용된다 — drain, descheduler
   등. `kubectl delete pod`나 스케일 다운 같은 직접 삭제에는 적용되지 않는다.
3. 복제본 수를 늘려 여유를 만드는 것. `minAvailable`을 낮추면 "항상 보장되는 최소 가용 개수"
   자체가 줄어들어 서비스 안정성 기준이 낮아지지만, 복제본을 늘리면 안정성 기준은 그대로
   지키면서 여유만 생긴다.
</details>

---

다음 장: [14. etcd 백업 / 복구](14-etcd-backup-restore.md)
