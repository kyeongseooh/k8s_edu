# 12. NetworkPolicy — Pod 사이의 방화벽

> 이 장도 **사고 대응 실습** 형식입니다: 정상 상태 → 실제 장애 유발 → 증거 → (막히면 펼쳐보는)
> 복구 → 성공 판정 → 정리. 0장에서 배정받은 개인 네임스페이스(`$NS`)를 그대로 쓰고, 리소스
> 이름(`billing-db`, `checkout-app`, `scanner-bot` 등)은 다른 장과 겹치지 않게 지었습니다.
> 네임스페이스를 새로 만들거나 지우지 않습니다.

## 1. 개념

쿠버네티스의 기본 동작은 다소 충격적입니다: **모든 Pod는 서로 자유롭게 통신할 수 있습니다.**
웹 Pod든, 다른 팀의 Pod든, 누구나 DB Pod에 접속을 시도할 수 있다는 뜻입니다.

**NetworkPolicy(네트워크폴리시)** 는 Pod 수준의 **방화벽 규칙**입니다.
"DB Pod에는 프론트엔드 Pod만, 80 포트로만 접속 허용" 같은 제어를 할 수 있습니다.

구성 요소는 3가지입니다.

- **podSelector**: 이 정책을 **적용받을** Pod 선택 (레이블로)
- **Ingress**(수신 규칙): 선택된 Pod로 **들어오는** 트래픽을 누가/어디서 보낼 수 있는지
- **Egress**(송신 규칙): 선택된 Pod에서 **나가는** 트래픽이 어디로 갈 수 있는지

> **중요한 동작 원리 — 화이트리스트**: 어떤 Pod가 NetworkPolicy의 대상으로 **선택되는 순간**,
> 그 방향(Ingress/Egress)의 트래픽은 **기본 전부 차단**되고, 정책에 명시된 것만 허용됩니다.
> "차단 규칙을 추가"하는 게 아니라 "허용 목록을 작성"하는 방식입니다.

> **전제 조건**: NetworkPolicy는 네트워크 플러그인(CNI)이 지원해야 동작합니다.
> Calico, Cilium 등은 지원하고, Flannel(기본형)은 지원하지 않습니다. 지원하지 않는 환경에서는
> 정책을 만들어도 **조용히 무시**되니 주의하세요. (이 실습은 지원 CNI를 전제로 합니다.)

## 2. YAML 뜯어보기 (참고용 — 적용하지 않음)

실무에서 자주 보는 "교과서형" 전체 예시입니다. ipBlock/namespaceSelector/podSelector를 함께
보여주기 위한 것이라, 이 장 실습에서는 **적용하지 않고 읽기만** 합니다.
([examples/12-networkpolicy/netpol.yaml](../examples/12-networkpolicy/netpol.yaml))

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-network-policy
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
    ports:
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

> **YAML 함정**: `from:` 아래 `-`로 나열된 항목들은 **OR** 관계입니다. `- namespaceSelector`와
> `podSelector`를 **한 항목 안에**(대시 하나에) 같이 쓰면 **AND**가 됩니다. 들여쓰기와 대시
> 하나로 의미가 완전히 달라지니 조심하세요.

## 3. 준비 — Pod 3개

```bash
k apply -f examples/12-networkpolicy/lab-pods.yaml
k wait --for=condition=Ready pod/billing-db pod/checkout-app pod/scanner-bot --timeout=60s
```

| Pod | 레이블 | 역할 |
|---|---|---|
| `billing-db` | `role=db` | 보호 대상 |
| `checkout-app` | `role=frontend` | 정당한 클라이언트 |
| `scanner-bot` | `role=hacker` | 침입자(항상 막혀야 함) |

## 4. 정상 상태 만들기 — 정책 적용

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
k apply -f examples/12-networkpolicy/netpol-db.yaml

DB_IP=$(k get pod billing-db -o jsonpath='{.status.podIP}')

echo "--- checkout-app → db (기대: 성공) ---"
if OUT=$(k exec checkout-app -- wget -qO- --timeout=3 "http://$DB_IP" 2>&1); then
  echo "PASS: 접속 성공"; printf '%s\n' "$OUT" | head -c 40; echo
else
  echo "FAIL: 접속 실패 (기대와 다름) — $OUT"
fi

echo "--- scanner-bot → db (기대: 타임아웃, 차단) ---"
if OUT=$(k exec scanner-bot -- wget -qO- --timeout=3 "http://$DB_IP" 2>&1); then
  echo "FAIL: 차단되어야 하는데 접속에 성공했다 — $OUT"
else
  echo "PASS: 타임아웃으로 차단됨 (기대한 결과) — $OUT"
fi
```

여기까지가 **정상 상태**입니다: 정당한 클라이언트(`checkout-app`)는 `PASS: 접속 성공`, 침입자
(`scanner-bot`)는 `PASS: 타임아웃으로 차단됨`이 찍혀야 합니다. 둘 다 `--timeout=3` 덕분에
3초 안에 반드시 끝납니다(무한 대기 없음). `wget`이 타임아웃되면 종료 코드가 0이 아니므로
`if/else`가 실제 성공/차단을 정확히 구분합니다 — 무조건 `|| true`로 넘기지 않습니다.

## 5. 장애 발생 — "배포했는데 체크아웃이 DB에 접속 못 해요"

운영팀이 `checkout-app`을 새 버전으로 배포하면서, 실수로 레이블을 `role=checkout`으로
바꿔버렸다고 합시다 (오타/배포 스크립트 실수를 재현).

```bash
k label pod checkout-app role=checkout --overwrite
```

증상 재현:

```bash
echo "--- checkout-app → db (지금은?) ---"
if OUT=$(k exec checkout-app -- wget -qO- --timeout=3 "http://$DB_IP" 2>&1); then
  echo "접속 성공 (아직 장애 아님) — $OUT"
else
  echo "타임아웃! 정당한 클라이언트인데도 차단됨 (장애 재현됨) — $OUT"
fi
```

### 증거 / 질문

```bash
k get pod checkout-app --show-labels
# role=checkout            ← 지금 레이블

k get networkpolicy db-allow-frontend -oyaml | grep -A3 podSelector
# (ingress.from[].podSelector) matchLabels: role: frontend   ← 정책이 기대하는 레이블
```

- NetworkPolicy 자체는 바뀐 게 없습니다. 그런데 왜 접속이 안 될까요?
- 정책을 느슨하게 고치는 것(예: `role: frontend` 조건 삭제)과, Pod 레이블을 원래대로 돌리는 것
  중 어느 쪽이 "장애의 진짜 원인"을 고치는 길일까요?

## 6. 복구 (막혔을 때만 펼쳐보세요)

<details><summary>복구 절차 보기</summary>

원인은 NetworkPolicy가 아니라 **배포 과정에서 잘못 붙은 레이블**이었습니다. 정책을 느슨하게
바꾸지 말고, Pod 레이블을 올바르게 되돌립니다.

```bash
k label pod checkout-app role=frontend --overwrite
k get pod checkout-app --show-labels
# role=frontend
```

</details>

## 7. 성공 판정

```bash
echo "--- checkout-app → db (기대: 성공) ---"
if OUT=$(k exec checkout-app -- wget -qO- --timeout=3 "http://$DB_IP" 2>&1); then
  echo "PASS: 접속 성공"; printf '%s\n' "$OUT" | head -c 40; echo
else
  echo "FAIL: 여전히 차단됨 — $OUT"
fi

echo "--- scanner-bot → db (기대: 여전히 차단) ---"
if OUT=$(k exec scanner-bot -- wget -qO- --timeout=3 "http://$DB_IP" 2>&1); then
  echo "FAIL: 차단되어야 하는데 접속에 성공했다 (정책이 느슨해졌을 가능성) — $OUT"
else
  echo "PASS: 타임아웃으로 여전히 차단됨 — $OUT"
fi
```

두 가지가 모두 `PASS`여야 성공입니다: ① 정당한 클라이언트는 다시 접속 성공, ② 침입자는 여전히
차단(정책을 느슨하게 풀어서 "고친 척"한 게 아님을 재확인).

## 8. 정리

```bash
k delete networkpolicy db-allow-frontend
k delete pod billing-db checkout-app scanner-bot
```

## 확인 문제

1. NetworkPolicy가 없는 기본 상태에서 Pod 간 통신은 어떻게 되는가?
2. 이번 장애의 원인은 정책이었나, 레이블이었나? 정책을 느슨하게 풀어서 고치면 왜 위험한가?
3. NetworkPolicy를 만들었는데 아무 효과가 없다면 의심해 볼 것은?

<details><summary>정답 보기</summary>

1. 전부 허용 — 모든 Pod가 서로 자유롭게 통신 가능
2. 레이블(배포 실수)이 원인이었다. 정책을 느슨하게 풀면(예: `role: frontend` 조건 제거) 당장은
   증상이 사라지지만, `scanner-bot`(침입자)도 같이 뚫려버려 보안 사고로 이어질 수 있다.
3. CNI(네트워크 플러그인)가 NetworkPolicy를 지원하는지 — Flannel 등은 지원하지 않아 조용히
   무시된다
</details>

---

다음 장: [13. Cordon / Drain — 노드 점검 준비](13-cordon-drain.md)
