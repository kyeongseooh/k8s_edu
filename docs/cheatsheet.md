# 장애 접수 후 첫 5분 — kubectl 치트시트

먼저 **대상**을 확인한다. [00장에서 만든 `k` 함수](00-시작하기-전에.md)는 현재 연습 중인 컨텍스트와 개인 네임스페이스를 지정한다. 아래 `<이름>`은 실제 이름으로 바꾼다. 운영에서는 조회로 증거를 모으고 변경은 승인된 범위에서만 한다.

```bash
printf 'context=%s namespace=%s\n' "$EDU_CONTEXT" "$NS"
k get deploy,rs,pod,svc -o wide
k get events --sort-by=.metadata.creationTimestamp
```

| 증상 | 처음 확인할 증거 | 다음 판단 |
|---|---|---|
| 배포했는데 Pod가 없다 | `k get rs`, `k describe rs <이름>` | 생성 자체가 거부됐나? quota, 정책, ServiceAccount를 본다. |
| `Pending` | `k describe pod <이름>`의 Events | `FailedScheduling`이면 [라벨·taint](15-scheduling.md), [CPU 요청](17-resources.md), [미바인딩 PVC](06-pv-pvc.md)를 문구로 구분한다. |
| `CreateContainerConfigError` | `k describe pod <이름>` | [ConfigMap](04-configmap.md)/[Secret](05-secret.md) 이름과 키가 같은 namespace에 존재하는가? 값을 출력할 필요는 없다. |
| `ImagePullBackOff` | Pod Events의 이미지 이름·태그와 pull 오류 | 잘못된 태그, 레지스트리 권한, 연결 실패를 구분한다. |
| `CrashLoopBackOff` | `k logs <Pod> -c <컨테이너> --previous`, `k describe pod <Pod>` | 마지막 종료 원인/코드를 본다. 아직 한 번도 시작하지 않았다면 로그 대신 Events. |
| `Running`인데 0/1 Ready | `k describe pod <Pod>`와 EndpointSlice의 `conditions.ready` | [readiness](16-probes.md) 실패는 프로세스 종료와 다르다. |
| Service 요청 실패 | `k get svc <서비스> -o yaml`, `k get pod --show-labels`, `k get endpointslice -l kubernetes.io/service-name=<서비스> -o yaml` | [selector](03-service.md) → 준비된 주소 → `targetPort` → [NetworkPolicy](12-networkpolicy.md) 순으로 좁힌다. |
| 클러스터 내부 요청만 성공 | `k describe ingress <이름>` | [Ingress](10-ingress.md) class, Host, 경로, backend Service/port를 본다. 404만으로 원인을 단정하지 않는다. |
| `Forbidden` | `k auth can-i <동사> <리소스>` | [RBAC](11-rbac.md) 주체·범위·동사를 확인한다. 앱 HTTP 403과 Kubernetes API의 Forbidden은 다르다. |
| 배치 `Completed` 또는 `Failed` | `k get jobs`, `k logs job/<이름>` | [Job](18-batch.md)은 종료가 정상일 수 있다. `Complete` 조건과 결과물을 확인한다. |

### 배포 이력과 복구에 자주 쓰는 명령

```text
k rollout status deploy/<앱> --timeout=90s   # 새 버전 배포가 완료됐나?
k rollout history deploy/<앱>                # 되돌아갈 Pod 템플릿 이력이 있는가?
k rollout undo deploy/<앱>                   # 앱의 Pod 템플릿 복구. Secret·DB는 복구하지 않는다.
k logs <Pod> -c <컨테이너> --tail=50          # 로그에 민감값이 없는지 확인 후 공유
k top pod                                    # metrics-server가 있을 때 실제 사용량 (예약량과 다름)
k apply --dry-run=server -f <파일>           # API/정책 검사. 실제 배치·네트워크·볼륨 성공 보장은 아님.
```

### 인수인계 메모 양식

`시각 / context·namespace / 사용자 증상 / 정상과 달라진 관측값 / 변경한 한 가지 / 같은 요청으로 얻은 복구 증거 / 남은 영향`. 재시작·삭제 전에 Events와 이전 로그를 확보한다. Secret·토큰·고객 데이터는 메모에 붙이지 않는다. 노드 점검이나 전체 복구가 필요하다면 [13장](13-cordon-drain.md)·[14장](14-etcd-backup-restore.md)의 보류 기준과 함께 운영 담당자에게 넘긴다.
