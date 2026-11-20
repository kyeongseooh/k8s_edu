# 15. 스케줄링 — 빈 노드가 있는데 왜 Pending일까?

스케줄러는 먼저 Pod가 **갈 수 없는 노드**를 걸러 낸 뒤 남은 후보의 점수를 비교한다. `nodeSelector`는 Pod 쪽의 요구(“이 라벨이 붙은 곳만”), **taint**는 노드 쪽의 제한(“이 사유를 감당하지 못하면 오지 마”)이다. **toleration은 제한을 견딜 수 있다는 표시이지 그리로 보내라는 예약이 아니다.** GPU 전용 풀이라면 일반 앱을 막는 taint와 GPU 작업을 그 풀에 보내는 라벨 조건을 따로 설계한다.

| 설정 | 스케줄러가 읽는 뜻 |
|---|---|
| `nodeSelector` | 적은 라벨을 **모두** 만족해야 한다. |
| node affinity `requiredDuringSchedulingIgnoredDuringExecution` | 배치 필수 조건. `In`, `Exists` 같은 표현식 가능. 배치 후 라벨 변경만으로 축출하지 않는다. |
| node affinity `preferredDuringSchedulingIgnoredDuringExecution` | 선호 조건. 후보가 없으면 다른 곳에도 배치할 수 있다. |
| taint `NoSchedule` / `PreferNoSchedule` | 각각 새 배치를 금지 / 가급적 회피. 기존 Pod를 쫓아내지 않는다. |
| taint `NoExecute` | 맞는 toleration이 없는 기존 Pod도 축출 대상. `tolerationSeconds`가 있으면 그 시간만 견딘다. |

예를 들어 `dedicated=batch:NoSchedule`에 맞는 **Pod spec 조각**은 아래와 같다. `Equal`은 key와 value가 맞아야 하고, `Exists`는 해당 key의 어떤 값이든 허용한다. 효과(`effect`)까지 명시하면 다른 제한까지 실수로 허용하지 않는다. 여러 taint가 있으면 각각 따진다.

```yaml
nodeSelector:
  workload: batch
tolerations:
- key: dedicated
  operator: Equal
  value: batch
  effect: NoSchedule
```

**현장에서 이미 작동 중인 예:** kube-proxy 방식의 클러스터라면, 네트워크를 준비하는 시스템 DaemonSet은 관리 노드에서도 돌아야 한다. 강사에게 `kube-system` 조회 권한이 있을 때만 아래 두 출력을 비교하자. `operator: Exists`에 key와 effect까지 비어 있다면 모든 taint를 허용하는 표현이다. 모든 노드의 네트워크를 맡은 구성 요소와 일반 웹 앱은 요구가 다르므로 그대로 복사하지 않는다.

```text
kubectl -n kube-system get daemonset kube-proxy -o jsonpath='{.spec.template.spec.tolerations}{"\n"}'
kubectl -n kube-system get pods -l k8s-app=kube-proxy -o wide
```

## 과제: 일반 웹 앱이 관리 노드만 요구하는 배포 사고

[준비](00-시작하기-전에.md) 후 [Deployment](../examples/15-scheduling/web.yaml)를 사용한다. **전제:** 다음 조회에서 `node-role.kubernetes.io/control-plane` 라벨과 같은 키의 `NoSchedule` taint가 있는 관리 노드, 그리고 일반 워커가 있어야 한다. 그렇지 않은 환경은 관찰 예제만 읽는다. 노드에 라벨이나 taint를 추가하지 않는다.

```bash
kubectl --context "$EDU_CONTEXT" get nodes -L node-role.kubernetes.io/control-plane
kubectl --context "$EDU_CONTEXT" get nodes -l node-role.kubernetes.io/control-plane -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints'
k apply -f examples/15-scheduling/web.yaml
k rollout status deploy/placement --timeout=120s
k get pod -l app=edu-placement -o wide
```

업무 상황: 배포자가 필수 affinity를 잘못 넣었다. 새 Pod가 어느 노드를 요구하는지, 워커와 관리 노드가 **각각 왜** 후보에서 빠졌는지 Events에서 찾자. [변경분 YAML](../examples/15-scheduling/wrong-affinity.patch.yaml)의 마지막 `Exists`는 **노드에 그 라벨이 있어야** 한다는 뜻이다. 이 장은 고장을 관찰하기 위해 작은 `Recreate` 배포를 쓰므로, 정상 Pod가 내려가고 다음 명령에서 타임아웃이 나는 것이 의도한 결과다.

```bash
k patch deploy placement --type=merge --patch-file examples/15-scheduling/wrong-affinity.patch.yaml
k rollout status deploy/placement --timeout=15s || true
k wait pod -l app=edu-placement,exercise=misplaced --for=condition=PodScheduled=false --timeout=45s
k describe pod -l app=edu-placement,exercise=misplaced
```

<details><summary>힌트와 복구: toleration을 넓혀야 할까?</summary>

`FailedScheduling`의 `untolerated taint`와 `didn't match Pod's node affinity/selector`를 구분한다. 관리 노드의 taint를 지우거나 모든 제한을 허용하는 것은 문제를 잘못 고치는 방식이다. 다음은 **내 API 요청만 서버 dry-run**하여 해당 taint의 toleration 표기법을 확인하는 예다. `Exists`라서 값이 없다. 스케줄러는 dry-run 객체를 보지 않으며 관리 노드에 Pod를 실행하지 않는다.

```bash
k patch deploy placement --dry-run=server --type=merge -p '{"spec":{"template":{"spec":{"tolerations":[{"key":"node-role.kubernetes.io/control-plane","operator":"Exists","effect":"NoSchedule"}]}}}}' -o jsonpath='{.spec.template.spec.tolerations}{"\n"}'
k patch deploy placement --type=merge -p '{"spec":{"template":{"metadata":{"labels":{"exercise":null}},"spec":{"affinity":null}}}}'
k rollout status deploy/placement --timeout=120s
k get pod -l app=edu-placement -o wide
k exec deploy/placement -- wget -q -O /dev/null http://127.0.0.1/
```

성공 기준은 일반 워커에 배치되고 HTTP가 성공하는 것이다. 운영에서는 선언 원본(Git)의 잘못된 affinity도 수정한다.
</details>

```bash
k delete -f examples/15-scheduling/web.yaml
```

다음: [16. 상태 검사](16-probes.md) · 함께 읽기: [DaemonSet](09-daemonset.md), [노드 점검](13-cordon-drain.md)
