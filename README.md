## 커리큘럼

| 장 | 주제 | 한 줄 요약 |
|---|------|-----------|
| [00](docs/00-시작하기-전에.md) | 시작하기 전에 | 컨테이너와 쿠버네티스가 왜 필요한가 + 실습 환경 준비 |
| [01](docs/01-pod.md) | Pod | 쿠버네티스에서 프로그램이 실행되는 가장 작은 단위 |
| [02](docs/02-deployment.md) | Deployment | Pod를 여러 개 띄우고, 죽으면 되살리고, 무중단 업데이트 |
| [03](docs/03-service.md) | Service | 계속 바뀌는 Pod의 IP 대신 고정된 주소로 접근하기 |
| [04](docs/04-configmap.md) | ConfigMap | 설정값을 코드와 분리해서 관리하기 |
| [05](docs/05-secret.md) | Secret | 비밀번호, 토큰 같은 민감한 값 관리하기 |
| [06](docs/06-pv-pvc.md) | PV / PVC | Pod가 사라져도 데이터는 남게 하는 저장소 |
| [07](docs/07-statefulset.md) | StatefulSet | 이름과 데이터가 유지되어야 하는 프로그램(DB 등) 실행 |
| [08](docs/08-headless-service.md) | Headless Service | Pod 하나하나를 직접 찾아가는 주소 체계 |
| [09](docs/09-daemonset.md) | DaemonSet | 모든 서버에 하나씩 실행해야 하는 프로그램 |
| [10](docs/10-ingress.md) | Ingress | 하나의 입구로 여러 서비스를 노출하기 (URL 라우팅) |
| [11](docs/11-rbac.md) | RBAC | 누가 무엇을 할 수 있는지 권한 제어 |
| [12](docs/12-networkpolicy.md) | NetworkPolicy | Pod 사이의 네트워크 방화벽 |
| [13](docs/13-cordon-drain.md) | Cordon / Drain | 서버 점검을 위해 Pod를 안전하게 비우기 |
| [14](docs/14-etcd-backup-restore.md) | etcd 백업/복구 | 클러스터 전체 데이터의 백업과 복구 |


실습에 쓰는 YAML 파일은 [`examples/`](examples/) 폴더에 장별로 들어 있습니다.

```bash
# 예: 1장 Pod 실습
kubectl apply -f examples/01-pod/pod-edu.yaml
```


## 자주 쓰는 명령어 모음

[cheatsheet.md](docs/cheatsheet.md)에 kubectl 명령어를 상황별로 정리해 두었습니다. 실습 중 옆에 띄워 두고 보세요.
