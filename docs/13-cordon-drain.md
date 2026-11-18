# 13. Cordon / Drain — 서버 점검을 위해 노드를 안전하게 비우기

## 1. 개념

노드(서버)의 OS를 업데이트하거나 하드웨어를 점검해야 할 때, 그 위에서 돌고 있는 Pod들을
어떻게 해야 할까요? 그냥 서버를 꺼 버리면 서비스 장애가 납니다. 쿠버네티스는 이를 위한
두 단계 도구를 제공합니다.

### cordon — 출입 금지 팻말

- 해당 노드를 **스케줄링 대상에서 제외** — 새 Pod가 더 이상 배정되지 않음
- **기존에 돌던 Pod는 그대로** 둠

### drain — 배수(비우기)

- cordon(출입 금지) + **기존 Pod들을 쫓아내서 다른 노드로 옮김**
- 쫓겨난 Pod는 Deployment/StatefulSet 같은 컨트롤러가 다른 노드에 재생성해 줌
- 노드 업데이트/점검 직전에 사용

> **비유**: 식당 한 구역을 수리한다면 — cordon은 "신규 손님은 이 구역에 앉히지 마"
> (기존 손님은 식사 계속), drain은 "기존 손님도 모두 다른 구역으로 옮겨 드리고 구역을 비워"입니다.

## 2. 실습

### cordon / uncordon

```bash
kubectl cordon ks3.dd.io      # 노드 이름은 kubectl get nodes 로 확인
kubectl get nodes
```

```
NAME        STATUS                     ROLES    AGE   VERSION
ks3.dd.io   Ready,SchedulingDisabled   <none>   23d   v1.25.x
```

`SchedulingDisabled` — 새 Pod는 안 오지만, 기존 Pod는 `kubectl get pod -owide`로 보면 그대로 있습니다.

```bash
# 2장처럼 Deployment를 스케일해 보면, 새 Pod가 ks3에는 안 생기는 것을 확인할 수 있음
kubectl uncordon ks3.dd.io    # 점검 끝, 다시 스케줄 허용
```

### drain

```bash
kubectl drain ks3.dd.io --ignore-daemonsets
```

- `--ignore-daemonsets`: DaemonSet의 Pod(9장)는 "노드당 1개"가 숙명이라 다른 노드로 옮길 수 없으니
  무시하고 진행하라는 옵션. 거의 항상 필요합니다.
- 추가로 자주 쓰는 옵션: `--delete-emptydir-data` (emptyDir 볼륨 데이터 삭제 허용 —
  로컬 임시 데이터가 있는 Pod가 있을 때 필요)

drain이 끝나면 노드는 cordon 상태가 되고, Pod들은 다른 노드에서 다시 돌고 있습니다.
이제 서버를 재부팅하거나 점검하면 됩니다. 점검이 끝나면:

```bash
kubectl uncordon ks3.dd.io
```

> **주의**: uncordon해도 쫓겨났던 Pod들이 자동으로 "돌아오지는" 않습니다. 이후 새로 생기는
> Pod부터 그 노드에 배정될 수 있게 되는 것입니다.

## 3. 정리된 운영 순서

```
1. kubectl drain <노드> --ignore-daemonsets      # Pod 비우기
2. (OS 패치, 재부팅, 하드웨어 점검 등)
3. kubectl uncordon <노드>                       # 스케줄링 복귀
```

## 확인 문제

1. cordon과 drain의 차이 한 줄 요약은?
2. drain 시 `--ignore-daemonsets`가 필요한 이유는?
3. drain한 노드를 다시 사용하려면?

<details><summary>정답 보기</summary>

1. cordon은 "새 Pod만 금지"(기존 유지), drain은 "새 Pod 금지 + 기존 Pod도 다른 노드로 이동"
2. DaemonSet Pod는 노드당 1개가 원칙이라 다른 노드로 옮길 수 없기 때문에, 무시하지 않으면 drain이 거부된다
3. `kubectl uncordon <노드>`
</details>

---

다음 장: [14. etcd 백업 / 복구](14-etcd-backup-restore.md)
