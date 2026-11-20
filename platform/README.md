# Kubernetes 위에서 데이터 플랫폼 운영하기

**최종 미션:** 주문 금액 3개를 합산하는 Python 코드를 직접 빌드한다. Harbor에 올린 그 이미지로 Airflow DAG가 **별도 Kubernetes Pod**를 실행해 `report_ok rows=3 total=42`를 남기게 한다. 그 과정에서 “누가 Pod를 만들었나?”, “어떤 Git 커밋의 정책이 적용됐나?”, “Pod가 살아 있는 것과 DAG가 성공한 것을 어떻게 구분하나?”에 답해 보자.

두 저장소의 역할이 다르다. **여기(`k8s_edu/platform`)는 읽는 교재**다. **[k8s-platform-gitops](https://github.com/kyeongseooh/k8s-platform-gitops)는 Argo CD가 읽는 실제 설정 저장소(private)**다. GitHub에서 404가 뜨면 저장소 관리자에게 읽기 권한을 요청한다. 교재를 수정해도 배포는 바뀌지 않는다.

| 순서 | 실습 | 성공 증거 |
|---|---|---|
| 00 | [시작 전 역할·환경 확인](docs/00-start.md) | 기존 Airflow와 새 교육 대상의 이름·권한을 구분 |
| 01 | [Docker → Harbor](docs/01-image-harbor.md) | push한 이미지와 pull한 digest 일치, 합계 42 |
| 02 | [Git → Argo CD → Airflow 생성](docs/02-gitops.md) | Application에 표시된 revision과 원격 Git SHA 일치 |
| 03 | [Namespace·ResourceQuota·LimitRange를 Git으로 변경](docs/03-policy.md) | 정책 값뿐 아니라 새 Pod에 들어간 기본값, quota 초과 거부까지 확인 |
| 04 | [커스텀 이미지를 쓰는 Airflow DAG](docs/04-airflow.md) | 컨트롤러가 만든 task Pod에서 실행한 결과가 task log에 남음 |
| 05 | [Keycloak 로그인 → kubectl 권한](docs/05-keycloak-kubectl.md) | 사용자·그룹 신원과 네임스페이스별 허용/거부를 따로 확인 |
| 06 | [Prometheus·Grafana 모니터링](docs/06-observability.md) | Pod 상태, scheduler heartbeat, task 결과를 서로 다른 신호로 진단 |
| 07 | [MinIO S3 객체 운영](docs/07-minio.md) | 내 prefix PUT/GET 일치, 범위 밖 접근 거부 |
| 08 | [Kubeflow Profile·Notebook·Pipeline](docs/08-kubeflow.md) | 내 Profile에서 실행 결과와 artifact 위치 확인 |

**추천 진행:** 00~04는 같은 실습 환경에서 이어서 하고 06으로 결과를 관찰한다. 05·07·08은 독립적으로 배울 수 있다. 공유 클러스터의 기존 `airflow`를 실습 대상으로 사용하지 않는다. 제공된 매니페스트는 이름이 고정된 **단일 실습 환경용**이다. 여러 팀이 동시에 쓰려면 팀별 Git 경로·Application·namespace로 분리하고 소유권을 확인한다.

[실제 검증 결과와 미실행 단계](verification.md) · [공개용 작은 예제](examples/) · [Kubernetes 기초로 돌아가기](../README.md)
