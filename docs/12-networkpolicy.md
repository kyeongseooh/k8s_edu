# 12. NetworkPolicy — Pod 사이의 방화벽

## 1. 개념

쿠버네티스의 기본 동작은 다소 충격적입니다: **모든 Pod는 서로 자유롭게 통신할 수 있습니다.**
웹 Pod든, 다른 팀의 Pod든, 누구나 DB Pod에 접속을 시도할 수 있다는 뜻입니다.

**NetworkPolicy(네트워크폴리시)** 는 Pod 수준의 **방화벽 규칙**입니다.
"DB Pod에는 프론트엔드 Pod만, 6379 포트로만 접속 허용" 같은 제어를 할 수 있습니다.

구성 요소는 3가지입니다.

- **podSelector**: 이 정책을 **적용받을** Pod 선택 (역시 레이블로!)
- **Ingress**(수신 규칙): 선택된 Pod로 **들어오는** 트래픽을 누가/어디서 보낼 수 있는지
- **Egress**(송신 규칙): 선택된 Pod에서 **나가는** 트래픽이 어디로 갈 수 있는지

> **중요한 동작 원리 — 화이트리스트**: 어떤 Pod가 NetworkPolicy의 대상으로 **선택되는 순간**,
> 그 방향(Ingress/Egress)의 트래픽은 **기본 전부 차단**되고, 정책에 명시된 것만 허용됩니다.
> "차단 규칙을 추가"하는 게 아니라 "허용 목록을 작성"하는 방식입니다.

> **전제 조건**: NetworkPolicy는 네트워크 플러그인(CNI)이 지원해야 동작합니다.
> Calico, Cilium 등은 지원하고, Flannel(기본형)은 지원하지 않습니다. 지원하지 않는 환경에서는
> 정책을 만들어도 **조용히 무시**되니 주의하세요.

## 2. YAML 뜯어보기

"db 역할 Pod 보호"의 전형적인 예시입니다.
([examples/12-networkpolicy/netpol.yaml](../examples/12-networkpolicy/netpol.yaml))

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-network-policy
  namespace: default
spec:
  podSelector:              # ① 이 정책의 적용 대상: role=db 레이블이 붙은 Pod
    matchLabels:
      role: db
  policyTypes:              # ② 수신/송신 중 어느 쪽을 통제할지
  - Ingress
  - Egress
  ingress:                  # ③ 들어오는 트래픽 허용 목록
  - from:
    - ipBlock:                        # (a) 이 IP 대역에서 오는 것 허용
        cidr: 172.17.0.0/16
        except:                       #     단, 이 하위 대역은 제외
        - 172.17.1.0/24
    - namespaceSelector:              # (b) 이 레이블이 붙은 네임스페이스의 Pod 허용
        matchLabels:
          project: myproject
    - podSelector:                    # (c) 같은 네임스페이스에서 이 레이블의 Pod 허용
        matchLabels:
          role: frontend
    ports:                            # 허용하더라도 이 포트로만
    - protocol: TCP
      port: 6379
  egress:                   # ④ 나가는 트래픽 허용 목록
  - to:
    - ipBlock:
        cidr: 10.0.0.0/24
    ports:
    - protocol: TCP
      port: 5978
```

이 정책을 한국어로 번역하면:

- `role=db` Pod는,
- **수신**: ①172.17.0.0/16 대역(단 172.17.1.0/24 제외) ②project=myproject 네임스페이스의 Pod
  ③role=frontend Pod — 이 셋 중 하나에서 오는 **TCP 6379** 요청만 받을 수 있다.
- **송신**: 10.0.0.0/24 대역의 **TCP 5978** 로만 나갈 수 있다.
- 그 외의 모든 수신/송신은 차단.

> **YAML 함정 하나**: `from:` 아래 `-`로 나열된 항목들은 **OR** 관계(셋 중 하나라도 만족하면 허용)
> 입니다. 만약 `- namespaceSelector`와 `podSelector`를 **한 항목 안에**(대시 하나에) 같이 쓰면
> **AND**(그 네임스페이스이면서 그 레이블인 Pod)가 됩니다. 들여쓰기와 대시 하나로 의미가 완전히
> 달라지니 조심하세요.

## 3. 실습 — 차단되는 것 직접 보기

```bash
# 1) 보호 대상: redis 흉내 (role=db)
kubectl run db --image=nginx --labels="role=db" --port=80

# 2) 접속 시도자 2명: frontend와 침입자
kubectl run frontend --image=busybox --labels="role=frontend" -- sleep 3600
kubectl run intruder --image=busybox --labels="role=hacker" -- sleep 3600

# 3) 정책 적용 전: 둘 다 접속됨
DB_IP=$(kubectl get pod db -o jsonpath='{.status.podIP}')
kubectl exec frontend -- wget -qO- --timeout=3 $DB_IP   # HTML 응답 (성공)
kubectl exec intruder -- wget -qO- --timeout=3 $DB_IP   # HTML 응답 (성공)
```

이제 "role=db에는 role=frontend만 80 포트 접속 허용" 정책을 겁니다.
([examples/12-networkpolicy/netpol-db.yaml](../examples/12-networkpolicy/netpol-db.yaml))

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-allow-frontend
spec:
  podSelector:
    matchLabels:
      role: db
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: frontend
    ports:
    - protocol: TCP
      port: 80
```

```bash
kubectl apply -f examples/12-networkpolicy/netpol-db.yaml

# 4) 정책 적용 후
kubectl exec frontend -- wget -qO- --timeout=3 $DB_IP   # 성공
kubectl exec intruder -- wget -qO- --timeout=3 $DB_IP   # timeout! (차단됨)
```

frontend는 통과, intruder는 타임아웃 — 레이블 하나 차이로 방화벽이 동작합니다.

## 4. 실습 정리

```bash
kubectl delete networkpolicy db-allow-frontend
kubectl delete pod db frontend intruder
```

## 확인 문제

1. NetworkPolicy가 없는 기본 상태에서 Pod 간 통신은 어떻게 되는가?
2. Ingress 규칙과 Egress 규칙의 차이는?
3. NetworkPolicy를 만들었는데 아무 효과가 없다면 의심해 볼 것은?

<details><summary>정답 보기</summary>

1. 전부 허용 — 모든 Pod가 서로 자유롭게 통신 가능
2. Ingress는 대상 Pod로 "들어오는" 트래픽 허용 목록, Egress는 대상 Pod에서 "나가는" 트래픽 허용 목록
3. CNI(네트워크 플러그인)가 NetworkPolicy를 지원하는지 — Flannel 등은 지원하지 않아 조용히 무시된다
</details>

---

다음 장: [13. Cordon / Drain — 노드 점검 준비](13-cordon-drain.md)
