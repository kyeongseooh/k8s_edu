# 08. Kubeflow — 내 작업 공간에서 Notebook과 Pipeline 운영하기

**Profile**은 사용자의 논리적인 작업 공간(대응 namespace와 권한), **Notebook**은 작업을 멈출 때까지 자원을 쓰는 개발 서버, **Pipeline run**은 정해진 단계를 실행하는 작업이다. Kubeflow 웹 로그인, Kubernetes API 권한, S3 artifact 접근 권한은 서로 다른 세 문이다. 지금 로그인한 사용자의 Profile을 강사에게서 받고 시작한다. 다른 사용자의 Profile을 새로 만들거나 변경하지 않는다.

## 1. 내 Notebook을 띄우고 Pending 원인 찾기

1. Central Dashboard 상단에서 지급받은 **namespace/Profile** 선택 → **Notebooks → New Notebook**. 강사가 허용한 Jupyter 이미지를 선택하고 예를 들어 CPU `0.5`, 메모리 `1Gi`를 요청한다. quota와 LimitRange가 허용하는지 먼저 확인한다.
2. 볼륨 항목을 확인한다. 기본 workspace PVC를 새로 만들면 `Retain` 정책에서 Notebook 삭제 후에도 데이터/PV가 남을 수 있다. 공유 교육 클러스터에서는 **이미 지급받은 공간**이나 관리자가 승인한 일회용 저장소만 사용한다. 자료를 보존할 위치 없이 기본값으로 생성하지 않는다.
3. 이름이 `Ready`가 되면 **Connect → Terminal**에서 `python -c 'print(6 * 7)'`로 42를 확인한다. 화면에 안 보일 때는 먼저 Dashboard에서 선택한 namespace와 Notebook 소유자를 비교한다.

```bash
: "${KF_NS:?지급받은 Kubeflow Profile namespace}" "${NB:?내 Notebook 이름}"
kubectl auth can-i get notebooks.kubeflow.org -n "$KF_NS"
kubectl -n "$KF_NS" get notebook "$NB"
kubectl -n "$KF_NS" get pod -l "notebook-name=$NB" -o wide
kubectl -n "$KF_NS" get events --sort-by=.metadata.creationTimestamp
```

**장애 과제:** 터미널에서 조회하는 이름만 `$NB-typo`로 바꿔 `NotFound`를 확인하고, 같은 namespace의 목록에서 올바른 이름을 찾아 복구한다. 실제 Notebook이 `Pending`이면 Pod Events의 `Insufficient ...`, quota의 `FailedCreate`, PVC 상태를 구분한다. 웹 SSO만 있는 교육생은 kubectl 권한을 가정하지 말고 Events 조회를 강사에게 요청한다.

## 2. 두 단계 Pipeline과 artifact

[예제 `pipeline.py`](../examples/kubeflow/pipeline.py)는 첫 단계에서 작은 텍스트를 **Output Artifact**로 쓰고, 둘째 단계가 같은 artifact를 **Input**으로 읽는다. 두 Pod가 같은 로컬 디렉터리를 공유하는 것이 아니다. KFP가 메타데이터와 저장 위치를 연결한다.

```bash
# 교재 저장소 루트에서, 격리된 Python 3.11 환경 사용
W=$(mktemp -d)
python3.11 -m venv "$W/venv"
"$W/venv/bin/pip" install 'kfp==2.4.0'
"$W/venv/bin/python" platform/examples/kubeflow/pipeline.py "$W/edu-pipeline.yaml"
```

위 단계는 **클러스터 접속 없이 IR YAML을 컴파일**할 뿐이다. 실제 실행은 Dashboard에서 내 Profile 확인 → **Pipelines → Upload pipeline** → 생성한 파일 업로드 → **Create run**, 내 Experiment에 `name=learner`로 실행한다. 경량 Python component는 실행 중 KFP 패키지 설치가 필요할 수 있다. 외부 패키지 접근이 금지된 환경은 SDK가 포함된 승인 이미지를 먼저 준비한다.

**성공 판정:** Run graph의 두 단계가 모두 Succeeded이고 둘째 단계 로그에 `hello, learner`가 나온다. 첫 단계의 **Output artifacts**에서 artifact의 URI/메타데이터를 확인하고 둘째 단계의 입력과 대조한다. UI의 artifact 링크가 403이면 작업 성공과 **뷰어의 저장소 접근 권한**을 분리해 조사한다. 다른 팀의 key를 열거나 공용 버킷 권한을 넓히지 않는다.

**종료:** 실습 run/Experiment는 강사의 보존 정책대로 정리한다. Notebook은 Stop하거나 필요 없으면 본인 것만 Delete한다. PVC·artifact는 별도 수명이 있으므로 ‘Notebook 삭제 = 데이터 삭제’로 판단하지 않는다. Profile과 공용 KFP 서비스는 삭제하지 않는다.
