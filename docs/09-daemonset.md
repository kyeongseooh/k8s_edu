# 09. DaemonSet — 노드별 수집기가 사라졌을 때

**Deployment**에게는 “웹 서버를 총 3개 유지해 줘”, **DaemonSet**에게는 “조건에 맞는 노드 **각각**에 수집기를 한 개씩 유지해 줘”라고 요청한다. DaemonSet에 `replicas`가 없는 이유다. 노드별 로그 수집, 네트워크 에이전트, 노드 메트릭 수집이 대표 사례다. 새 노드가 조건을 만족하면 Pod가 자동으로 추가된다. 모든 노드를 뜻하지는 않는다. 노드 라벨, affinity, taint도 영향을 준다.

## 과제: 배포가 성공한 것 같은데 수집 대상 노드가 0대

[예제 YAML](../examples/09-daemonset/daemonset.yaml)은 노드 파일이나 로그를 읽지 않는 작은 HTTP 서버로 수집기를 대신한다. 전제는 **Ready 워커 2대 이상**, 노드 목록 조회 권한, 개인 공간의 DaemonSet 생성 권한이다. `kubectl get nodes`로 Ready 상태를 먼저 확인한다. 다음은 컨트롤 플레인이 아닌 워커의 **기존 hostname 라벨 값**만 읽는다. 노드에 새 라벨을 붙이지 않는다.

```bash
kubectl --context "$EDU_CONTEXT" get nodes -L kubernetes.io/hostname
mapfile -t workers < <(kubectl --context "$EDU_CONTEXT" get nodes -l '!node-role.kubernetes.io/control-plane,kubernetes.io/hostname' -o jsonpath='{range .items[*]}{.metadata.labels.kubernetes\.io/hostname}{"\n"}{end}')
printf '선택할 워커 후보: %s\n' "${workers[@]}"
```

목록의 첫 두 노드가 Ready이고 교육에 사용할 수 있는지 확인한다. 둘이 없으면 이 장을 건너뛴다. 예제의 `operator: In`은 등록한 값 중 하나와 일치하면 된다는 뜻이다. 다음 명령은 예제 **파일은 바꾸지 않고** 두 값을 채운 결과만 API에 보낸다.

```bash
w1=${workers[0]:?첫 번째 워커 필요}; w2=${workers[1]:?두 번째 워커 필요}
sed -e "s/WORKER_A/$w1/g" -e "s/WORKER_B/$w2/g" examples/09-daemonset/daemonset.yaml | k apply -f -
k rollout status ds/ch09-ds --timeout=120s
k get ds ch09-ds
k get pod -l app=ch09-ds -o wide
```

정상 기준은 `DESIRED=2`, `READY=2`이고 서로 다른 워커에 한 개씩이다. 이제 실수로 **내 DaemonSet**에 어떤 노드에도 없는 추가 필수 라벨을 요구한다.

```bash
k patch ds ch09-ds --type=merge -p '{"spec":{"template":{"spec":{"nodeSelector":{"training.example.invalid/missing":"yes"}}}}}'
k wait ds/ch09-ds --for=jsonpath='{.status.desiredNumberScheduled}'=0 --timeout=60s
k get ds ch09-ds
k get pod -l app=ch09-ds -o wide
k get ds ch09-ds -o jsonpath='{.spec.template.spec.nodeSelector}{"\n"}'
```

**질문:** `DESIRED=0`과 `DESIRED=2, READY=0`은 어떻게 다를까? 전자는 컨트롤러 관점에서 대상 노드가 없고, 후자는 대상이 있으나 Pod가 준비되지 않은 것이다. 전자에서는 Pending Pod조차 없을 수 있으므로 Pod 로그부터 찾으면 원인을 놓친다.

<details><summary>힌트와 복구</summary>

수집기 배포물의 조건이 잘못됐다. 모든 노드에 라벨을 붙이는 대신 **실습 DaemonSet 템플릿에서 그 조건만 제거**한다.

```bash
k patch ds ch09-ds --type=merge -p '{"spec":{"template":{"spec":{"nodeSelector":null}}}}'
k wait ds/ch09-ds --for=jsonpath='{.status.desiredNumberScheduled}'=2 --timeout=60s
k rollout status ds/ch09-ds --timeout=120s
k get pod -l app=ch09-ds -o wide
k exec ds/ch09-ds -- wget -qO /dev/null http://127.0.0.1/
```

성공 기준: 같은 두 워커에 다시 1개씩 배치되고 HTTP 요청이 성공한다.
</details>

```bash
k delete ds ch09-ds
```

다음: [10. Ingress](10-ingress.md) · 함께 읽기: [15. taint와 affinity](15-scheduling.md)
