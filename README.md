# 처음 맡은 Kubernetes 서비스 운영

**대상:** 터미널은 써 봤지만 Kubernetes에서 직접 서비스를 배포하거나 장애를 처리해 본 적이 없는 신입 직원. 목표는 YAML을 외우는 것이 아니라 **“어디에서 멈췄는지 증거로 설명하고, 고친 뒤 사용자 요청이 다시 성공함을 보이는 것”**이다.

**처음이라면 [00. 실습 환경 준비](docs/00-시작하기-전에.md)부터 시작한다.** 같은 Bash 셸에서 개인 네임스페이스를 가리키는 `k` 함수를 설정한 뒤, 저장소 루트에서 각 장의 명령을 실행한다. 각 장은 `examples/`의 자기 리소스를 만들고 정리하므로 필요한 장만 골라 다시 할 수 있다. 일부러 고장 내는 대상은 내 실습 앱뿐이다.

| 추천 순서 | 읽을 장 | 퇴근 전에 해 볼 일 |
|---|---|---|
| ① 첫 배포 | [00 준비](docs/00-시작하기-전에.md) → [01 Pod](docs/01-pod.md) → [02 Deployment](docs/02-deployment.md) → [03 Service](docs/03-service.md) | Pod가 실행되는 것과 Service로 요청이 전달되는 것을 구분한다. |
| ② 배포 설정과 안정성 | [04 ConfigMap](docs/04-configmap.md) · [05 Secret](docs/05-secret.md) → [16 상태 검사](docs/16-probes.md) · [17 자원 예약/상한](docs/17-resources.md) | 설정 누락, 준비 상태 실패, CPU 예약 오류를 서로 다른 증거로 찾는다. |
| ③ 저장소와 이름 | [06 PV/PVC](docs/06-pv-pvc.md) → [07 StatefulSet](docs/07-statefulset.md) → [08 Headless Service](docs/08-headless-service.md) | 저장소 요청·Pod 이름·DNS 중 어디가 고장인지 구분한다. |
| ④ 배치 위치와 작업 종류 | [15 스케줄링: taint/toleration과 affinity](docs/15-scheduling.md) → [09 DaemonSet](docs/09-daemonset.md) · [18 Job/CronJob](docs/18-batch.md) | `FailedScheduling`을 읽고, 계속 실행할 서버와 끝나야 하는 배치를 구분한다. |
| ⑤ 접근 경로와 권한 | [10 Ingress](docs/10-ingress.md) · [11 RBAC](docs/11-rbac.md) · [12 NetworkPolicy](docs/12-networkpolicy.md) | HTTP 라우팅, Kubernetes API 권한, Pod 간 통신 차단을 구분한다. |
| ⑥ 관리자와 협업 | [13 Cordon/Drain과 PDB](docs/13-cordon-drain.md) · [14 etcd 백업/복구](docs/14-etcd-backup-restore.md) | 노드 점검을 보류할 때와 복구 후보를 탈락시킬 때 근거를 제시한다. |

**수업 진행법:** 정상 요청 결과를 먼저 적는다 → 장애를 한 가지만 만든다 → 정답을 펼치기 전 관찰 명령 하나를 골라 이유를 설명한다 → 수정 후 **같은 요청**을 다시 해 본다 → 리소스를 정리한다. 짝 실습이라면 한 사람은 대응자, 다른 사람은 “무슨 증거로 그렇게 판단했나요?”를 묻는 동료가 된다.

- [증상별 kubectl 치트시트](docs/cheatsheet.md): 첫 증거와 다음에 볼 장을 연결한다.
- [검증 기록과 실습 범위](docs/verification.md): 실제 클러스터에서 수행한 단계와 모의·미검증 항목을 구분한다.
- 공용 환경에서 교육을 위해 노드 taint 변경, drain, etcd 복원, 클러스터 전체 권한 부여를 하지 않는다. 교육용 이미지는 재현을 위한 예제이며 운영 이미지의 보안·지원 기준을 대신하지 않는다.
