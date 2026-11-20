# 17. Requests / limits — 예약할 자리와 쓸 수 있는 상한

`requests`는 스케줄러가 노드에 자리를 잡을 때 계산하는 기준, `limits`는 실행 중 컨테이너가 쓸 수 있는 상한이다. 식당에 4인석을 **예약**하는 것과 주방이 받을 주문에 **한도**를 두는 것을 구분하자. `100m` CPU는 코어 0.1개, `32Mi` 메모리는 32 × 1024² 바이트다. 메모리를 `32m`로 쓰면 전혀 다른 단위가 된다.

| 관찰한 증상 | 어떤 단계인지 | 첫 증거 |
|---|---|---|
| `Pending` + `Insufficient cpu` | 배치 전. 워커의 현재 CPU 사용률이 낮아도 이미 예약된 양이 많을 수 있다 | Pod Events와 `kubectl describe node`의 Allocated resources |
| 느리지만 재시작은 없음 | 실행 중 CPU limit에서 throttling 가능 | 지연 시간과 CPU throttling 지표; `top`만으로 단정하지 않기 |
| `OOMKilled` | 실행 중 메모리 문제 | `lastState.terminated.reason`, limit와 노드 메모리 압력 둘 다 확인 |

## 과제: 단위 실수로 배포가 멈췄다

[Deployment](../examples/17-resources/worker.yaml)를 작게 배포한다. 아래 고장은 **예약 요청만** 크게 만든다. CPU 부하를 만들거나 워커 메모리를 소진하지 않는다.

```bash
k apply -f examples/17-resources/worker.yaml
k rollout status deploy/sized-worker --timeout=120s
k get deploy sized-worker -o jsonpath='{.spec.template.spec.containers[0].resources}{"\n"}'
k set resources deploy/sized-worker -c web --requests=cpu=9999,memory=8Mi --limits=cpu=9999,memory=32Mi
k rollout status deploy/sized-worker --timeout=15s || true
k get rs,pod -l app=edu-sized
k describe pod -l app=edu-sized
```

노드보다 큰 요청을 제출했다. 일반 실습 환경은 `FailedScheduling: Insufficient cpu`, 할당량이 있는 환경은 **Pod가 만들어지기 전에** ReplicaSet Events에 `FailedCreate`/`exceeded quota`가 보일 수도 있다. 두 경우를 구분한다. 템플릿 변경 자체를 정책이 거부했다면 오류 메시지를 증거로 기록한다.

<details><summary>힌트와 복구</summary>

Pod를 반복 삭제해도 컨트롤러가 같은 크기를 다시 요구한다. 템플릿의 예약량을 고친다. 운영 값은 실측 CPU·메모리 사용량과 부하 테스트에 맞춰 정한다.

```bash
k set resources deploy/sized-worker -c web --requests=cpu=10m,memory=8Mi --limits=cpu=100m,memory=32Mi
k rollout status deploy/sized-worker --timeout=120s
k exec deploy/sized-worker -- wget -qO /dev/null http://127.0.0.1/
k get pod -l app=edu-sized -o wide
```

성공 기준: Pending이 사라지고 새 Pod가 실제 요청을 처리한다.
</details>

```bash
k delete -f examples/17-resources/worker.yaml
```

다음: [18. Job과 CronJob](18-batch.md)
