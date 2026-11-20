# 16. Probe — 살아 있는 것과 손님을 받을 수 있는 것은 다르다

| kubelet이 묻는 질문 | 실패가 이어지면 | 실무 예 |
|---|---|---|
| `startupProbe`: 앱 기동이 끝났나? | 허용 횟수를 넘기면 컨테이너 재시작. 성공할 때까지 다른 두 검사는 보류 | 초기 파일을 오래 읽는 앱 |
| `readinessProbe`: 지금 요청을 받아도 되나? | Pod가 NotReady가 되고 일반 Service 트래픽 대상에서 제외. **재시작하지 않는다** | 준비 파일·요청 처리 가능 여부 |
| `livenessProbe`: 재시작하면 살아날 상태인가? | 연속 실패 시 컨테이너 재시작 | 앱 내부 교착. 외부 DB 장애를 여기 넣으면 멀쩡한 앱까지 재시작될 수 있다. |

[실습 YAML](../examples/16-probes/web.yaml)은 `/`로 기동·생존을, `/ready`로 준비 여부를 검사한다. `periodSeconds: 2`, `failureThreshold: 2`는 한 번 실패했다고 즉시 제외하지 않고 연속 실패를 확인하겠다는 뜻이다.

## 과제: 프로세스는 Running인데 Service가 보낼 곳이 없다

```bash
k apply -f examples/16-probes/web.yaml
k rollout status deploy/health-web --timeout=120s
k exec deploy/health-web -- wget -qO- http://health-web/ready
k get endpointslice -l kubernetes.io/service-name=health-web
```

`ready`가 출력되는 것을 확인한다. 배포 중 준비 파일이 누락된 상황을 **내 실습 Pod에서만** 만든다. `Running`, `READY`, `RESTARTS`를 따로 읽고 EndpointSlice 주소가 남아도 트래픽 대상인지 확인하자.

```bash
k exec deploy/health-web -- rm /usr/share/nginx/html/ready
k wait pod -l app=edu-health --for=condition=Ready=false --timeout=45s
k get pod -l app=edu-health
k describe pod -l app=edu-health
k wait endpointslice -l kubernetes.io/service-name=health-web --for=jsonpath='{.endpoints[0].conditions.ready}'=false --timeout=40s
k exec deploy/health-web -- wget -qO /dev/null http://127.0.0.1/
```

<details><summary>힌트와 복구</summary>

`Readiness probe failed`와 HTTP 404가 증거다. 프로세스와 `/`는 정상인데 Service 뒤에 준비된 Pod가 0개인 상황이다. 재시작 대신 진짜 누락된 조건을 복구한다.

```bash
k exec deploy/health-web -- sh -c 'printf ready > /usr/share/nginx/html/ready'
k wait pod -l app=edu-health --for=condition=Ready --timeout=45s
k wait endpointslice -l kubernetes.io/service-name=health-web --for=jsonpath='{.endpoints[0].conditions.ready}'=true --timeout=40s
k exec deploy/health-web -- wget -qO- http://health-web/ready
k get pod -l app=edu-health
```

성공 기준: **같은 Pod**의 재시작 횟수가 그대로이고 Service에서 다시 `ready`가 돌아온다. 실제 앱은 컨테이너 파일 수동 수정 대신 이미지나 준비 로직을 고쳐 배포한다.
</details>

```bash
k delete -f examples/16-probes/web.yaml
```

다음: [17. 리소스](17-resources.md)
