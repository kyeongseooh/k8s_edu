# 손으로 익히는 Kubernetes

쿠버네티스를 처음 만나는 사람을 위한 실습 교재입니다. 각 장은 **왜 필요한가 → 그림으로 보는 개념 → YAML 읽기 → 따라 하는 실습 → 일부러 고장 내고 고치기** 순서로 진행합니다.
읽기만 해서는 남지 않습니다. 명령을 직접 실행하고, 출력이 교재와 같은지 비교하면서 따라오세요.

## 시작하기

1. [00. 시작하기 전에](docs/00-시작하기-전에.md)에서 컨테이너와 쿠버네티스의 큰 그림을 보고, 실습용 네임스페이스를 준비합니다.
2. 아래 표의 순서대로 진행합니다. 앞 장에서 배운 것을 뒤 장에서 계속 사용합니다.
3. 모든 명령은 이 저장소를 내려받은 디렉터리(`README.md`가 보이는 곳)에서 실행합니다.

## 목차

| 단계 | 장 | 배우는 것 |
|---|---|---|
| 1. 앱 띄우기 | [01 Pod](docs/01-pod.md) → [02 Deployment](docs/02-deployment.md) → [03 Service](docs/03-service.md) | 컨테이너 실행, 자동 복구와 무중단 배포, 고정 주소로 접속하기 |
| 2. 설정 넣기 | [04 ConfigMap](docs/04-configmap.md) → [05 Secret](docs/05-secret.md) | 설정과 비밀 값을 이미지와 분리해서 전달하기 |
| 3. 데이터 지키기 | [06 PV/PVC](docs/06-pv-pvc.md) → [07 StatefulSet](docs/07-statefulset.md) → [08 Headless Service](docs/08-headless-service.md) | 영구 저장소, Retain/Delete 회수 정책, 고정된 이름을 가진 Pod |
| 4. 서비스 운영 | [09 DaemonSet](docs/09-daemonset.md) → [10 Ingress](docs/10-ingress.md) → [11 RBAC](docs/11-rbac.md) → [12 NetworkPolicy](docs/12-networkpolicy.md) | 노드마다 하나씩 띄우기, 외부 HTTP 진입점, 권한과 네트워크 차단 |
| 5. 클러스터 관리 | [13 Cordon/Drain](docs/13-cordon-drain.md) → [14 etcd 백업·복원](docs/14-etcd-backup-restore.md) → [15 스케줄링](docs/15-scheduling.md) | 노드 점검, 클러스터 상태 백업, Pod가 놓일 노드 정하기 |
| 6. 안정적으로 실행 | [16 Probe](docs/16-probes.md) → [17 Requests/Limits](docs/17-resources.md) → [18 Job/CronJob](docs/18-batch.md) | 상태 검사, 자원 예약과 상한, 한 번 실행하고 끝나는 작업 |

- **막혔을 때:** [증상별 치트시트](docs/cheatsheet.md)
- **기초 다음 과정:** [Kubernetes 위에서 데이터 플랫폼 운영하기](platform/README.md) — Harbor, Argo CD, Airflow, Keycloak, 모니터링과 스토리지

## 저장소 구성

```
docs/       장별 교재 (00 ~ 18, 치트시트)
examples/   장별 실습용 YAML
images/     교재에 쓰인 그림
platform/   기초 다음 과정 (플랫폼 운영)
```
