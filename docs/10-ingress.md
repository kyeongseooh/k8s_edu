# 10. Ingress — 세 경로 중 하나만 503이라면?

Service는 Pod들의 안정적인 **내부 주소**, Ingress는 HTTP 요청의 **Host와 경로를 어느 Service로 연결할지 정한 규칙**이다. Ingress 리소스가 스스로 요청을 처리하지는 않는다. IngressClass가 지정한 **컨트롤러가 작동 중**이어야 한다. 실습에서는 하나의 교육 호스트에 `/naver`, `/cloud`, `/platform` 세 경로를 두고 장애 범위를 좁혀 본다.

[세 개의 백엔드](../examples/10-ingress/deploysvc.yaml)는 경로 이름을 응답하는 nginx와 ClusterIP Service다. [Ingress 예제](../examples/10-ingress/ingress.yaml)의 `ingressClassName: nginx`는 이 규칙의 담당자를, `backend.service.port.number`는 **컨테이너 포트가 아니라 Service의 포트**를 가리킨다. `rewrite-target: /`은 이 컨트롤러가 백엔드에 원래 경로 대신 `/`를 요청하게 한다.


## 과제: 특정 경로만 장애

```bash
k apply -f examples/10-ingress/deploysvc.yaml
for app in naver cloud platform; do k rollout status deploy/ch10-"$app" --timeout=90s; done
# 파일 원본은 유지하고 교육생 개인 호스트만 치환해서 적용한다.
apply_routes() { sed "s/learner\.invalid/$LAB_HOST/g" examples/10-ingress/ingress.yaml | k apply -f -; }
apply_routes
route() { k exec deploy/ch10-naver -- wget -T 3 -qO- --header="Host: $LAB_HOST" "http://$CTRL_IP/$1"; }
# 컨트롤러가 규칙을 반영하는 데 시간이 걸린다.
for i in {1..20}; do if route cloud; then break; fi; sleep 2; done
for path in naver cloud platform; do route "$path"; done
```

각 응답이 경로의 이름과 같은 것이 정상이다. 이제 **내 호스트의 두 번째 경로(`/cloud`)만** 없는 backend Service를 가리키게 한다. 어느 구간까지 정상인지 형제 경로와 Service 직접 요청을 대조하자.

```bash
k patch ingress ch10-path-ingress --type=json -p='[{"op":"replace","path":"/spec/rules/0/http/paths/1/backend/service/name","value":"ch10-cloud-typo"}]'
for i in {1..20}; do if ! route cloud; then break; fi; sleep 2; done
route naver
k exec deploy/ch10-naver -- wget -T 3 -qO- http://ch10-cloud/
k describe ingress ch10-path-ingress
k get svc ch10-cloud
```

**질문:** `/cloud`는 오류지만 `ch10-cloud`로 직접 호출하면 여전히 `cloud`가 나온다. 이때 Pod를 재시작해도 소용없는 이유는? 오류 코드는 컨트롤러 구현에 따라 다를 수 있으므로 코드 하나만 보고 단정하지 않는다.

<details><summary>힌트와 복구: 정상인 구간을 제외하자</summary>

다른 경로가 응답하므로 입구 전체가 죽은 게 아니다. Service 직접 요청도 성공하므로 이 경우 Pod와 Service 사이도 정상이다. Ingress의 `/cloud` backend 이름만 정상 선언으로 되돌린다.

```bash
apply_routes
for i in {1..20}; do if route cloud; then break; fi; sleep 2; done
for path in naver cloud platform; do route "$path"; done
```

성공 기준: **같은 Host 헤더**로 세 경로 모두 다시 자기 이름을 응답한다.
</details>

```bash
k delete ingress ch10-path-ingress
k delete -f examples/10-ingress/deploysvc.yaml
```

다음: [11. RBAC](11-rbac.md)
