# 강사용: 무엇을 어디까지 검증했나

이 기록은 특정 클러스터의 한 번의 결과이지, 다른 환경에서의 동작을 보증하지 않는다. **실행**은 정상 준비 → 장애 증거 → 복구 확인 → 정리를 실제로 수행했다는 뜻이다. **API 검증**은 서버가 객체를 검증했지만 실행하지 않았다는 뜻이고, **모의**는 실환경 장애 대신 교육용 증거를 판독했다는 뜻이다.

- 검증일: 2026-11-20. Kubernetes/kubectl v1.29.15, Ready 노드 5대. 관리 노드에 기존 `NoSchedule`, 워커 4대, Calico CNI, nginx IngressClass, 기본 동적 StorageClass의 회수 정책 `Retain`.
- 각 과제는 별도의 일회용 네임스페이스에서 수행했다. 교재에서 지시하는 권한 거부·실패 이벤트·HTTP 비정상은 테스트 실패가 아니라 **관찰 대상**이다. 복구는 별도의 신호로 확인한다.

- 결과: 00~18장 과제 검증 완료(14장은 모의). 독립 YAML 파일 38개를 서버 `--dry-run=server --validate=strict`로 검사했고, 나머지 1개는 독립 객체가 아닌 15장의 패치로 실제 적용했다. 종료 후 검증용 namespace·해당 namespace를 참조하는 PV가 없고 노드 5대는 계속 Ready였다.

| 장 | 검증 방식 | 장애 증거 → 복구 증거 |
|---|---|---|
| 00 | 실행 | 잘못 쓴 라벨 필터가 빈 결과 → 실제 라벨을 확인한 뒤 같은 ConfigMap에서 `training` 조회 |
| 01 | 실행 | 맞지 않는 nodeSelector로 `FailedScheduling` → 정상 Pod를 다시 만들어 Pod 이름이 담긴 HTTP 응답 확인 |
| 02 | 실행 | 존재하지 않는 nginx 태그에서 `ImagePullBackOff` → rollout undo 후 Service에서 `Welcome to nginx` 확인 |
| 03 | 실행 | selector 오타로 Service의 대상 주소가 사라지고 호출 실패 → selector 복구 후 Service 이름으로 다시 웹 응답 |
| 04 | 실행 | ConfigMap의 `usernam` 키를 찾지 못해 `CreateContainerConfigError` → 올바른 키 참조 후 앱 환경변수에서 교육용 값 확인 |
| 05 | 실행 | 모의 Secret에 없는 `env2` 키 오류와 Secret 볼륨 쓰기 거부 → 키 참조를 고쳐 Pod Ready 및 모의 값 확인 |
| 06 | 실행 + API 검증 | 없는 StorageClass의 `ProvisioningFailed`, 오타 난 claimName의 `FailedScheduling … not found` 관찰 → `emptyDir` 앱에서 쓰기·읽기 성공. 정상 PVC는 서버 dry-run만 수행. **실제 PV 바인딩·영속 데이터 복원은 미검증** |
| 07 | 실행 | StatefulSet의 0번 Pod를 다시 만들자 이름은 그대로이고 UID는 바뀌며 임시 파일 HTTP 404 → 원본을 다시 써서 HTTP 응답 확인. 실제 DB/PV 복구 실습이 아님 |
| 08 | 실행 | Headless Service selector 오타 → 대상 주소가 비고 캐시 만료 후 고정 이름 `NXDOMAIN`, Pod IP 직접 요청은 성공 → selector 복구 후 같은 고정 이름으로 `ch08-app-1` 응답 |
| 09 | 실행 | 워커 2곳에 한 개씩 → 충족 불가능한 추가 조건으로 DaemonSet `DESIRED=0` → 조건 제거 후 2개 Ready 및 HTTP 성공 |
| 10 | 실행 (컨트롤러 경유) | 잘못된 backend 이름 탓에 `/cloud`만 HTTP 503. `/naver`와 `ch10-cloud` 직접 호출은 정상 → 올바른 규칙 재적용 후 세 경로 모두 정상 응답. 외부 DNS·TLS는 미검증 |
| 11 | 실행 | 존재하지 않는 Role을 가리켜 `get pods` 거부 → RoleBinding 수정 후 `get`은 허용, `delete`는 계속 거부 |
| 12 | 실행 | 허용 대상 클라이언트의 라벨을 바꾸자 HTTP 타임아웃 → 라벨 복구 후 해당 클라이언트만 성공하고 비교 Pod는 계속 차단 |
| 13 | 실행 (실습 앱만) | 4개 복제본에서 점검 여유 1 → 3개로 축소하면 `disruptionsAllowed=0` → 4개로 복귀해 1. 실제 cordon·drain·축출은 미실행 |
| 14 | 모의 (명령 실행) | 최신 가상 파일의 SHA-256 불일치로 후보 제외 → 이전 파일 선택, 예상 유실 구간 3초를 RPO 목표 60초와 비교. 실제 etcd 접근·백업·복원 없음 |
| 15 | 실행 + API 검증 + 읽기 전용 관찰 | 스케줄러가 관리 노드 1대는 `untolerated taint`, 워커 4대는 affinity 불일치로 제외 → 잘못된 조건 제거 후 워커에서 HTTP 성공. 관리 노드 toleration 추가는 **서버 dry-run만** 수행. 기존 kube-proxy의 `Exists`와 관리 노드 배치는 조회로 확인 |
| 16 | 실행 | readiness HTTP 404, EndpointSlice `ready=false`, localhost는 정상 → 파일 복구 후 같은 Pod가 재시작 없이 Service에서 `ready` 응답 |
| 17 | 실행 | 워커 4대 `Insufficient cpu` → 예약량 수정 후 1/1 Ready 및 HTTP 성공. 부하 발생·OOM은 실행하지 않음 |
| 18 | 실행 | 잘못된 입력으로 종료 코드 2, Job 실패 → 템플릿 수정 후 새 Job `Complete`, `report generated: daily`. 정기 트리거는 중지 상태로 두고 수동 Job으로 검증 |

## 다음 기수에서 다시 확인할 때

1. 새 교육 클러스터인지 컨텍스트를 확인하고 [00장](00-시작하기-전에.md)의 개인 공간을 먼저 준비한다. 동명이인이 있거나 예전 실습이 남은 공간을 재사용하지 않는다.
2. 로컬 문법 검사는 저장소 루트에서 `python3 -I tools/check_materials.py` (Python 3, PyYAML, Bash 필요). 상대 링크·Bash 구문·예제 YAML을 확인할 뿐 클러스터에 접근하지 않는다.
3. 각 장 순서대로 정상 → 고장 → 복구를 따라가며 위 표의 **양쪽** 신호를 기록한다. CNI/IngressClass, 권한, 노드 라벨, PV 회수 정책이 다르면 먼저 해당 장의 전제를 확인한다. 오류를 없애기 위해 공용 노드나 정책을 바꾸지 않는다.
4. 각 장 정리 후 00장 절차로 본인이 만든 네임스페이스만 삭제하고 사라졌는지 확인한다. 실제 서비스의 로그·접속 정보·Secret을 교육 기록에 옮기지 않는다.
