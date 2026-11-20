# 01. 코드를 이미지로 만들고 Harbor에서 다시 받아 보기

**상황:** 개발자의 노트북에서 된 Python 작업을 Airflow에서도 똑같이 돌리고 싶다. Airflow scheduler에 Python 패키지를 직접 설치하는 대신 **작업 전용 이미지**를 만든다. DAG는 이미지에 들어 있는 작업을 언제, 어디서 실행할지 지시한다.

## 1. 빌드와 로컬 테스트 — 제작자 PC

[GitOps 저장소](https://github.com/kyeongseooh/k8s-platform-gitops)의 루트에서 실행한다. Dockerfile은 `report.py`만 복사하고, 숫자 사용자(65532)로 실행한다. [공개 소스](../examples/task/)로도 이 단계는 재현할 수 있다. 교육 클러스터와 CPU 아키텍처가 다르면 해당 worker용 이미지를 빌드하거나 multi-arch로 게시한다.

```bash
TAG=$(git rev-parse --short=12 HEAD)
docker build -t "edu-report:$TAG" images/task
docker run --rm "edu-report:$TAG"                       # report_ok rows=3 total=42
docker run --rm "edu-report:$TAG" --amounts 2,3,5        # total=10
rc=0; docker run --rm "edu-report:$TAG" --amounts 1,bad || rc=$?
printf '잘못된 입력 종료 코드: %s (기대: 2)\n' "$rc"
```

## 2. Harbor로 push — 제작자 계정

강사: **Projects → New Project**에서 교육용 private 프로젝트를 만들고, **Robot Accounts**에서 이 프로젝트에만 권한을 준다. publisher는 repository **pull+push**, reader는 **pull만** 부여한다. 관리자 계정으로 `docker login`하거나 관리자 인증 정보를 `imagePullSecret`으로 만들지 않는다.

사설 CA이면 관리자가 **신뢰된 경로로 전달한 CA**를 빌드 엔진에 먼저 등록한다. Linux Docker Engine의 registry별 위치는 `/etc/docker/certs.d/<호스트[:포트]>/ca.crt`이다. worker의 containerd 신뢰 설정은 별도다. `curl --cacert` 성공과 kubelet pull 성공은 같은 검사가 아니다. `x509: certificate signed by unknown authority`는 잘못된 비밀번호가 아니다. `--insecure`로 넘기지 않는다.

```bash
: "${HARBOR_HOST:?강사가 준 호스트명만 입력 (https:// 제외)}" "${HARBOR_PROJECT:?교육 프로젝트}"
REPO="$HARBOR_HOST/$HARBOR_PROJECT/report"
PUSH_CONFIG=$(mktemp -d); chmod 700 "$PUSH_CONFIG"
read -r -p 'publisher robot 이름: ' PUB_USER
read -rs -p 'publisher secret: ' PUB_PASS; printf '\n'
printf '%s' "$PUB_PASS" | docker --config "$PUSH_CONFIG" login "$HARBOR_HOST" -u "$PUB_USER" --password-stdin
unset PUB_PASS
docker tag "edu-report:$TAG" "$REPO:$TAG"
docker --config "$PUSH_CONFIG" push "$REPO:$TAG"
docker --config "$PUSH_CONFIG" logout "$HARBOR_HOST"
```

## 3. 실행 권한으로 독립 검증 — reader

별도 임시 설정으로 **reader** 로그인 후 pull한다. `tag`는 사람이 붙이는 이름이어서 재지정될 수 있다. `digest`는 실제 콘텐츠 식별자다. **Harbor → 프로젝트 → Repositories → report → Artifacts**에서 같은 SHA-256인지 대조한다.

```bash
PULL_CONFIG=$(mktemp -d); chmod 700 "$PULL_CONFIG"
read -r -p 'reader robot 이름: ' PULL_USER
read -rs -p 'reader secret: ' PULL_PASS; printf '\n'
printf '%s' "$PULL_PASS" | docker --config "$PULL_CONFIG" login "$HARBOR_HOST" -u "$PULL_USER" --password-stdin
unset PULL_PASS
docker --config "$PULL_CONFIG" pull "$REPO:$TAG"
IMAGE=$(docker image inspect "$REPO:$TAG" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep -F "$REPO@sha256:" | head -1)
[[ -n $IMAGE ]] && docker run --rm "$IMAGE"
```

**Git에 넣을 것:** `clusters/training/task-image.properties`의 `image=호스트/프로젝트/report@sha256:…` 한 줄. **넣지 않을 것:** 두 Docker 설정 디렉터리. [02장](02-gitops.md)에서 교육 namespace 생성 후 reader의 `config.json`만 Kubernetes Secret으로 등록한다. 그 직후 로그아웃하고 본인이 만든 임시 디렉터리만 정리한다. 이미지가 참조 중이면 Harbor artifact를 지우지 않는다.

**장애 대응:** `unauthorized/denied`면 CA가 아니라 robot의 프로젝트·동사를 확인한다. `manifest unknown`이면 호스트/프로젝트/태그·digest가 맞는지 본다. pull 성공 뒤 `exec format error`가 나면 이미지와 worker의 아키텍처를 비교한다. 합격 기준은 push 성공 메시지가 아니라 **reader가 같은 digest를 받아 동일한 계산 결과를 낸 것**이다.
