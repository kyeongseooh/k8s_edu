# kubectl 치트시트

실습 중 옆에 띄워 두고 보는 명령어 모음입니다. `k`는 `alias k=kubectl` 기준입니다.

## 기본 패턴

모든 리소스에 똑같이 적용되는 만능 패턴:

```bash
kubectl get <리소스>                  # 목록
kubectl get <리소스> <이름> -oyaml    # 상세를 YAML로
kubectl describe <리소스> <이름>      # 상세 + 이벤트 (디버깅 1순위)
kubectl apply -f <파일.yaml>          # 생성/수정
kubectl delete -f <파일.yaml>         # 파일에 정의된 것 일괄 삭제
kubectl delete <리소스> <이름>        # 개별 삭제
```

리소스 이름은 줄여 쓸 수 있습니다:
`pod=po`, `service=svc`, `deployment=deploy`, `replicaset=rs`, `statefulset=sts`,
`daemonset=ds`, `configmap=cm`, `namespace=ns`, `ingress=ing`, `persistentvolumeclaim=pvc`

## 조회

```bash
k get pod                        # 현재 네임스페이스의 Pod
k get pod -A                     # 모든 네임스페이스
k get pod -n kube-system         # 특정 네임스페이스
k get pod -owide                 # 노드/IP 컬럼 추가
k get pod --show-labels          # 레이블 표시
k get pod -l app=edu-app         # 레이블로 필터
k get pod -w                     # 실시간 변화 관찰 (Ctrl+C로 종료)
k get all                        # pod/svc/deploy 등 한꺼번에
k get nodes                      # 노드 목록
k get events --sort-by=.lastTimestamp   # 최근 이벤트
```

## 디버깅 3종 세트

```bash
k describe pod <이름>            # ① 이벤트 확인 (스케줄 실패, 이미지 pull 실패 등)
k logs <pod이름>                 # ② 앱의 출력 (-f: 실시간, --previous: 죽기 전 로그)
k exec -it <pod이름> -- bash     # ③ 컨테이너 안으로 (bash 없으면 sh)
```

## 생성 (명령형 — 빠른 실험용)

```bash
k run mypod --image=nginx                        # Pod 하나
k create deployment myapp --image=nginx          # Deployment
k expose deployment myapp --type=NodePort --port=80   # Service
k create configmap mycm --from-literal=k=v --from-file=f.txt
k create secret generic mysec --from-literal=pw=1234
k create namespace myns
k create sa mysa
```

> 팁: `--dry-run=client -oyaml` 을 붙이면 실제로 만들지 않고 YAML 뼈대만 출력해 줍니다.
> `k create deploy myapp --image=nginx --dry-run=client -oyaml > deploy.yaml`

## Deployment 운영

```bash
k scale deploy myapp --replicas=5                # 개수 조절
k set image deploy myapp <컨테이너>=<이미지:태그>  # 이미지 교체 (롤링 업데이트)
k rollout status deploy myapp                    # 진행 상황
k rollout history deploy myapp                   # 리비전 이력
k rollout undo deploy myapp                      # 롤백
k rollout undo deploy myapp --to-revision=1      # 특정 리비전으로
k rollout restart deploy myapp                   # 전체 재시작 (설정 리로드 등)
```

## 레이블

```bash
k label pod mypod env=dev            # 추가
k label pod mypod env=prod --overwrite   # 수정
k label pod mypod env-                # 제거 (key 뒤에 -)
k label nodes <노드> type=worker      # 노드에 레이블
```

## 권한 (RBAC)

```bash
k auth can-i create pod                          # 내가 할 수 있나?
k auth can-i delete sts -n <ns> --as=system:serviceaccount:<ns>:<sa>   # 그 계정은?
```

## 노드 운영

```bash
k cordon <노드>                      # 신규 스케줄 금지
k drain <노드> --ignore-daemonsets   # Pod 비우기 (점검 전)
k uncordon <노드>                    # 복귀
k top nodes / k top pods             # 자원 사용량 (metrics-server 필요)
```

## 자주 겪는 상태와 대처

| 상태 | 의미 | 먼저 볼 것 |
|------|------|-----------|
| `Pending` | 스케줄될 노드가 없음 | `describe` — 자원 부족? nodeSelector 오타? |
| `ContainerCreating` | 이미지 받는 중/볼륨 붙이는 중 | 오래 걸리면 `describe` — pull 실패? PVC 미바인딩? |
| `ImagePullBackOff` | 이미지 못 받음 | 이미지 이름/태그 오타, 프라이빗 레지스트리 인증(imagePullSecrets) |
| `CrashLoopBackOff` | 시작하자마자 죽기를 반복 | `logs --previous` — 앱 에러 확인 |
| `Completed` | 정상 종료 (Job 등) | 이상 아님 |
