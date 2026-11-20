# 강사용 검증표 — 실제로 어디까지 동작했나?

검증일: **2026-11-20**. 대상 클러스터 Kubernetes 1.29.15. 이 표에서 **실측**은 실제 서비스 응답, **격리 실행**은 로컬 빌드·Docker·SDK에서 확인한 결과다. 렌더링이나 DAG import를 실제 Argo 동기화 또는 DAG run 성공으로 세지 않는다.

| 구간 | 검증과 결과 |
|---|---|
| Docker → Harbor | **실측.** 비루트 Python 작업 이미지 빌드 → `report_ok rows=3 total=42`. 잘못된 입력은 exit 2. 인증된 Kubernetes 경로에서 Harbor의 공개 CA만 받아 TLS 검증. 전용 private 프로젝트에 publisher robot으로 push, 별도 reader robot으로 같은 digest pull 후 정상 실행. 실측 digest `sha256:488089a81531598076837768a92b685750d3072d258e522e563512946ab0e4fe` |
| Git과 정책 변경 | **실측.** [private GitOps 저장소](https://github.com/kyeongseooh/k8s-platform-gitops) 생성·push. [`9a23a4d` 초기 정책](https://github.com/kyeongseooh/k8s-platform-gitops/commit/9a23a4d) → [`da73cdf` Airflow·DAG·RBAC·모니터](https://github.com/kyeongseooh/k8s-platform-gitops/commit/da73cdf) → [`8f2b2bb` 정책만 변경](https://github.com/kyeongseooh/k8s-platform-gitops/commit/8f2b2bb). 전후 렌더에서 Pod quota 8→10, CPU 기본 요청 25m→50m 확인 |
| Argo CD → 교육 namespace | **미적용.** 기존 `airflow` Application의 chart/버전·동기화 상태만 조회. 보호된 `argocd` namespace에 새 repo 인증/프로젝트/Application을 등록하는 작업이 세션 권한 경계에서 거부되어 실행하지 않았다. 따라서 교육 앱의 `Synced/Healthy`, live quota 반영, 교육 task Pod의 kubelet pull은 주장하지 않는다. 강사는 [02장](docs/02-gitops.md)·[03장](docs/03-policy.md)에서 승인된 등록과 실제 리비전 대조를 수행한다. |
| Airflow | **격리 실행.** 실제 `apache/airflow:2.10.4` 이미지의 DagBag import 오류 없음. DAG `edu_image_report`, KPO provider 10.0.1, `edu-task` SA 및 Harbor digest 참조 확인. 계산 이미지는 실제 실행했지만 kube-apiserver로 task Pod를 만드는 DAG run은 위 이유로 미실행 |
| Prometheus·Grafana | **실측 + 격리 실행.** 기존 `airflow` namespace로 phase·재시작·CPU·scheduler 가용 복제본을 쿼리해 네 쿼리 모두 시계열 반환. Grafana 자체 health API의 DB 응답 `ok`. 기존 Airflow StatsD 비활성 및 Airflow 전용 시계열 없음 확인. 격리 Docker에서 **실제 Airflow scheduler** → UDP → exporter HTTP로 `edu_airflow_scheduler_heartbeat_total 1`, 별도 `edu_smoke_test 1` 관측. 클러스터 ServiceMonitor scrape·Grafana 개인 패널 저장·task success/failure 시계열은 미검증 |
| Keycloak → kubectl | **전제 확인.** 기존 API 서버에 OIDC/authentication-config 플래그가 없고 제공 웹 주소는 HTTP. 공유 API 서버나 realm을 수정하지 않았다. 실제 `auth whoami`·그룹 권한 검증은 HTTPS issuer 및 전용 client 구성 뒤의 강사 과제 |
| MinIO | **실측.** 콘솔은 HTML, S3 API는 객체 API와 health 응답으로 구분. SSH로 보호한 연결에서 임시 전용 버킷과 prefix 한정 STS 세션 사용. PUT → GET 바이트 일치, 같은 테스트 버킷의 허용 밖 prefix 쓰기 403, 생성한 객체·버킷 정리 확인 |
| Kubeflow | **실측 + 컴파일.** Profile/Notebook API와 설치된 워크로드를 읽기 전용으로 확인. Python 3.11/KFP SDK 2.4.0에서 교육 pipeline을 IR YAML(schema 2.1.0)로 컴파일하고 `system.Artifact` 입출력 확인. 공유 Profile의 Notebook 생성이나 Pipeline 업로드·run은 실행하지 않음 |

**남긴 것:** 재수업용 두 저장소와 교육용 Harbor artifact. **회수한 것:** 테스트 전용 Harbor robot 2개와 Git 읽기 전용 deploy key. 학생이 위 이미지를 사용할 때는 새 pull 전용 자격 증명을 발급한다. 공용 SSO·Airflow·모니터 설정을 변경하지 않았고, 교육용 Argo Application이나 namespace를 설치하지 않았다. 계정이나 접속 정보가 담긴 관리자 UI 캡처는 게시하지 않았다.

정적 검증: 교육 Kustomize 리소스 14개, bootstrap 2개, OIDC RBAC 예제 2개를 **지정 클러스터에서 조회한 OpenAPI v2 스키마**와 오프라인 대조해 18개 모두 통과했다. CRD 종류와 필드 검증이지 admission webhook·스케줄링·권한 성공을 뜻하지 않는다.

재검증: 교재 루트에서 `python3 -I platform/tools/check.py --gitops /path/to/k8s-platform-gitops` (Bash, kubectl, PyYAML 필요). 상대 링크·Bash 구문·Python 예제와 Kustomize 결과의 ConfigMap 참조를 확인한다. 라이브 동기화 검증은 이 명령과 별개다.
