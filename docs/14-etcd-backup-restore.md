# 14. etcd 백업 / 복구 — 스냅샷 근거를 읽는 법

> 이 장은 **실제 etcd 파일/Secret/백업/읽기/복구를 전혀 수행하지 않습니다.** 운영 클러스터의
> etcd에 손대는 건 위험도가 매우 높기 때문에, 대신 **가상 스냅샷(그냥 로컬 텍스트 파일)** 을
> 만들어서 "해시로 무결성을 확인하고, 예상 데이터 유실 구간을 RPO(복구 시점 목표)와 비교하는" **근거
> 판독 연습**을 합니다. 모든 작업은 `mktemp -d`로 만든 임시 디렉터리 안에서만 이루어지며,
> 쿠버네티스 클러스터나 기존 파일은 수정하지 않습니다 (다른 수강생과 경로가
> 겹칠 일이 없습니다).

## 1. 개념

지금까지 만든 모든 것(Pod, Deployment, Service, Secret, 정책...)의 정의와 상태는 **etcd**라는
분산 key-value 데이터베이스에 저장됩니다. 컨트롤 플레인 노드에서 돌며, 클러스터의 **유일한
진실의 원천(source of truth)** 역할을 합니다.

- etcd가 날아가면 = **클러스터의 모든 설정이 날아감**
- 백업은 **스냅샷(snapshot)** 방식: 특정 시점의 전체 데이터를 파일 하나로 저장
- 실제로는 실행 중인 etcd의 스냅샷을 `etcdctl snapshot save`로 만들며, 현대 버전에서 오프라인 검사·복원은 `etcdutl`이 담당합니다.

> **Python 비유**: etcd 스냅샷은 SQLite `.db` 파일을 통째로 복사해 두는 것과 비슷합니다.
> 사고가 나면 그 파일로 되돌립니다.

### 스냅샷을 다룰 때 반드시 확인할 3가지

1. **해시(무결성)** — 스냅샷 파일이 저장/전송 중 손상되지 않았는지. 생성 직후 계산해 둔
   해시값과, 복구하려는 시점에 다시 계산한 해시값이 같아야 "믿을 수 있는" 스냅샷입니다.
2. **시점(타임스탬프)** — 이 스냅샷이 언제 찍힌 것인지. 장애 발생 시각과 비교해서 **얼마나
   오래된 데이터로 되돌아가는지**를 알아야 합니다.
3. **RPO(Recovery Point Objective)** — "최대 이 정도까지만 데이터를 잃어도 된다"는 **목표치**
   (예: "RPO 60초"). 실제 사고가 나면, "장애 발생 시각 − 실제로 쓸 수 있었던 가장 최근의
   정상 스냅샷 시각"을 계산해서 나오는 값은 **실제(예상) 손실 구간**이며, 이것과 RPO 목표를
   **비교**해서 목표를 지켰는지 판단합니다. 이 실습에서도 두 값을 구분해서 다룹니다
   (`RPO_TARGET_SECONDS` = 목표, `ACTUAL_LOSS_SECONDS` = 실제 손실 구간).

> **해시 일치가 복구를 보장하지는 않음**: 해시가 일치한다는 건 "저장/전송 중 파일이
> 손상되지 않았다"는 것만 확인해 줍니다. etcd 내부 데이터 일관성, 복구 절차 자체의 성공
> 여부는 별개의 문제입니다. 실제 운영에서는 `etcdutl snapshot status`로 스냅샷의 내부
> 상태(revision, key 개수 등)까지 추가로 확인합니다. 이 실습은 "해시/시점 판독" 단계까지만
> 다룹니다.

> **PV 데이터는 별도**: etcd 스냅샷에는 Pod/Deployment/Secret 같은 **API 리소스 정의**만
> 들어있습니다. PV(PersistentVolume)에 실제로 쓰인 **애플리케이션 데이터(파일, DB 내용)는
> etcd 백업에 포함되지 않습니다.** PV 데이터는 별도의 볼륨 스냅샷/백업 도구(예: CSI
> VolumeSnapshot, Velero)로 따로 보호해야 합니다.

> **etcdctl / etcdutl 버전 주의**: etcd 3.5부터 `snapshot restore`가 `etcdctl`에서 `etcdutl`로
> 옮겨졌습니다. 클라이언트 도구 버전과 etcd 서버 버전이 다르면 스냅샷 포맷/명령이 호환되지
> 않을 수 있으므로, 실제 운영에서는 **백업을 만든 환경과 복구할 환경의 etcdctl/etcdutl
> 버전을 반드시 맞춰야** 합니다.

## 2. 준비 — 실습용 임시 디렉터리

```bash
REPO_ROOT=$(pwd)
RPO_TARGET_SECONDS=60   # 이번 사고 대응의 목표: "최대 60초치 데이터까지만 잃는다"
WORKDIR=$(mktemp -d /tmp/etcd-lab.XXXXXX)
echo "WORKDIR=$WORKDIR"
cd "$WORKDIR"
```

> `mktemp -d`는 매번 고유한 디렉터리를 만들어 주므로, 같은 호스트를 여러 수강생이 함께
> 써도 경로가 겹치지 않습니다. `REPO_ROOT`는 정리 단계에서 저장소 루트로 돌아오기 위해
> 미리 기억해 둡니다.

스냅샷 메타데이터 형식 참고용 (적용/실행하지 않는 참고 파일):
([examples/14-etcd-backup-restore/snapshot-metadata-example.json](../examples/14-etcd-backup-restore/snapshot-metadata-example.json))

```json
[
  { "file": "etcd-snap-0001.db", "taken_at_epoch": 1731000000, "sha256": "<해시>" },
  { "file": "etcd-snap-0002.db", "taken_at_epoch": 1731003600, "sha256": "<해시>" }
]
```

## 3. 정상 상태 만들기 — 가상 스냅샷 2개 생성

"etcd-snap-0001"(1차 백업)과 "etcd-snap-0002"(2차 백업)를 만들고, 생성 직후 해시를
`snapshots.tsv`에 기록합니다 (실제 백업 운영에서 반드시 해야 하는 절차입니다).

```bash
printf 'cluster-state-v1\n' > etcd-snap-0001.db
T1=$(date -u +%s)
H1=$(sha256sum etcd-snap-0001.db | awk '{print $1}')
printf '%s\tetcd-snap-0001.db\t%s\n' "$T1" "$H1" > snapshots.tsv

sleep 2   # 유한 대기: 두 스냅샷의 시점을 구분하기 위함 (2초)

printf 'cluster-state-v2\n' > etcd-snap-0002.db
T2=$(date -u +%s)
H2=$(sha256sum etcd-snap-0002.db | awk '{print $1}')
printf '%s\tetcd-snap-0002.db\t%s\n' "$T2" "$H2" >> snapshots.tsv

cat snapshots.tsv
```

## 4. 장애 발생 — 스냅샷 저장소 손상 + 클러스터 사고

두 가지 일이 동시에 벌어집니다 (실무에서 흔한 패턴: 모니터링이 못 잡은 백업 손상 + 그 뒤에
실제 장애).

```bash
# ① 가장 최신 백업(0002)이 저장 중 손상됐는데, 메타데이터는 갱신되지 않음
printf 'CORRUPTED-BYTES' >> etcd-snap-0002.db

sleep 1
# ② 장애 발생 시각 기록
INCIDENT_TIME=$(date -u +%s)
echo "INCIDENT_TIME=$INCIDENT_TIME"
```

### 증거 / 질문

각 스냅샷의 "지금 다시 계산한 해시"와 "생성 직후 기록해 둔 해시"를 비교합니다.

```bash
while IFS=$'\t' read -r ts file recorded_hash; do
  current_hash=$(sha256sum "$file" | awk '{print $1}')
  if [ "$current_hash" = "$recorded_hash" ]; then
    echo "OK   $file (ts=$ts) 해시 일치 → 신뢰 가능"
  else
    echo "BAD  $file (ts=$ts) 해시 불일치 → 손상, 복구에 쓰면 안 됨"
  fi
done < snapshots.tsv
```

- 어떤 스냅샷이 "손상되어 못 쓰는" 파일인가요?
- 손상된 스냅샷을 빼고 나면, 실제로 복구에 쓸 수 있는 **가장 최근** 스냅샷은 무엇인가요?
- 그 스냅샷 시점과 `INCIDENT_TIME`의 차이가 바로 이번 사고의 **실제(예상) 손실 구간**입니다.
  몇 초(실무라면 몇 분/시간)일까요? 목표(`RPO_TARGET_SECONDS`=60초)를 지킬 수 있을까요?

## 5. 복구 (막혔을 때만 펼쳐보세요)

<details><summary>판독 절차 보기</summary>

손상된 스냅샷(해시 불일치)은 후보에서 제외하고, 해시가 일치하는 것 중 **가장 최신**
스냅샷을 복구 시점으로 선택합니다. 이 실습에서는 `etcd-snap-0001.db`만 해시가 일치하므로
그것이 유일한 복구 후보입니다.

```bash
# 해시가 일치하는 스냅샷만 골라서, 그중 가장 최신 타임스탬프를 선택
BEST_TS=""
BEST_FILE=""
while IFS=$'\t' read -r ts file recorded_hash; do
  current_hash=$(sha256sum "$file" | awk '{print $1}')
  if [ "$current_hash" = "$recorded_hash" ]; then
    if [ -z "$BEST_TS" ] || [ "$ts" -gt "$BEST_TS" ]; then
      BEST_TS="$ts"
      BEST_FILE="$file"
    fi
  fi
done < snapshots.tsv

echo "복구에 쓸 스냅샷: $BEST_FILE (ts=$BEST_TS)"

ACTUAL_LOSS_SECONDS=$((INCIDENT_TIME - BEST_TS))
echo "실제(예상) 손실 구간 = ${ACTUAL_LOSS_SECONDS}초 (이 시간 동안의 변경사항은 복구 후 사라짐)"
echo "RPO 목표 = ${RPO_TARGET_SECONDS}초"

if [ "$ACTUAL_LOSS_SECONDS" -le "$RPO_TARGET_SECONDS" ]; then
  echo "목표 충족: 실제 손실(${ACTUAL_LOSS_SECONDS}초) <= 목표(${RPO_TARGET_SECONDS}초)"
else
  echo "목표 초과: 실제 손실(${ACTUAL_LOSS_SECONDS}초) > 목표(${RPO_TARGET_SECONDS}초) — 백업 주기를 더 짧게 가져가야 함"
fi
```

> 실제 운영이라면 여기서 버전에 맞는 `etcdutl snapshot restore` 절차 로 복구하지만,
> 이 실습은 "어떤 스냅샷을 써야 하는지, 얼마나 손실이 나는지"를 판단하는 단계까지만
> 다룹니다. 해시가 일치해도 `etcdutl snapshot status`로 내부 상태를 한 번 더 확인하기 전에는
> "복구 가능"이라고 단정하지 않습니다.

</details>

## 6. 성공 판정

```bash
EXPECT_BEST="etcd-snap-0001.db"
if [ "$BEST_FILE" = "$EXPECT_BEST" ] && [ "$ACTUAL_LOSS_SECONDS" -gt 0 ]; then
  echo "PASS: 손상된 스냅샷(0002)을 제외하고 0001을 올바르게 선택했고, 실제 손실 구간(${ACTUAL_LOSS_SECONDS}초)도 계산됨"
else
  echo "FAIL: 선택한 스냅샷 또는 손실 구간 계산이 기대와 다름 (BEST_FILE=$BEST_FILE, ACTUAL_LOSS_SECONDS=$ACTUAL_LOSS_SECONDS)"
fi
```

이 실습 조건(스냅샷 간격 2초, 손상 전 sleep 1초)에서는 `ACTUAL_LOSS_SECONDS`가 `RPO_TARGET_SECONDS`
(60초)보다 훨씬 작게 나옵니다 — 즉 목표를 충족합니다. 반대로 백업 주기가 길었다면(예: 하루에
한 번) 같은 계산 방식으로 목표를 초과하는 상황도 똑같이 판별할 수 있습니다.

## 7. 정리

```bash
cd "$REPO_ROOT"
rm -rf "$WORKDIR"
```

## 확인 문제

1. etcd 스냅샷에 포함되지 않는 것은 무엇이며, 그건 어떻게 별도로 보호해야 하는가?
2. 스냅샷의 해시가 기록해 둔 값과 다르면 무엇을 의미하는가? 해시가 일치하면 복구가
   보장되는가?
3. RPO(목표)와 이번 실습에서 계산한 `ACTUAL_LOSS_SECONDS`(실제 손실 구간)는 어떻게 다른가?

<details><summary>정답 보기</summary>

1. PersistentVolume(PV)에 담긴 실제 애플리케이션 데이터. etcd 백업은 API 리소스 정의만
   담으므로, PV 데이터는 CSI VolumeSnapshot이나 Velero 같은 별도 도구로 백업해야 한다.
2. 스냅샷 파일이 생성 이후 손상되었거나 변조되었다는 뜻 — 그 스냅샷으로 복구하면 안 된다.
   다만 해시가 일치해도 그것만으로 복구가 100% 보장되는 것은 아니다 — 해시는 "파일이
   손상되지 않았다"만 확인해 줄 뿐, etcd 내부 일관성이나 복구 절차의 성공 여부는 별개이며
   실제로는 `etcdutl snapshot status` 등으로 추가 확인이 필요하다.
3. RPO는 "최대 이 정도까지만 잃어도 된다"는 **목표치**이고, `ACTUAL_LOSS_SECONDS`는 실제
   사고에서 "장애 발생 시각 − 쓸 수 있었던 가장 최근 정상 스냅샷 시각"으로 계산한 **실제
   (예상) 손실 구간**이다. 실제 손실이 목표보다 크면 백업 주기를 더 짧게 가져가야 한다는
   신호다.
</details>

---

🎉 수고하셨습니다! 전체 과정을 마쳤습니다. [cheatsheet.md](cheatsheet.md)를 옆에 두고
직접 이것저것 만들어 보는 것이 가장 좋은 복습입니다.
