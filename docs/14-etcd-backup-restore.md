# 14. etcd 백업 / 복구 — 클러스터의 두뇌를 지키기

## 1. 개념

지금까지 만든 모든 것(Pod, Deployment, Service, Secret, 정책...)의 정의와 상태는 어디에
저장될까요? 바로 **etcd**라는 분산 key-value 데이터베이스입니다. 컨트롤 플레인 노드에서 돌며,
클러스터의 **유일한 진실의 원천(source of truth)** 역할을 합니다.

- etcd가 날아가면 = **클러스터의 모든 설정이 날아감**
- 그래서 etcd 백업은 쿠버네티스 운영의 가장 기본적인 재해 대비책
- 백업은 **스냅샷(snapshot)** 방식: 특정 시점의 전체 데이터를 파일 하나로 저장

> **Python 비유**: etcd 스냅샷은 SQLite `.db` 파일을 통째로 복사해 두는 것과 비슷합니다.
> 사고가 나면 그 파일로 되돌립니다.

작업은 **컨트롤 플레인 노드에서**, `etcdctl`이라는 etcd 전용 CLI로 합니다.

## 2. 백업

etcd는 TLS로 보호되고 있어서 인증서 3종을 지정해야 접근할 수 있습니다.
(kubeadm 설치 기준, 인증서는 `/etc/kubernetes/pki/etcd/`에 있습니다)

```bash
sudo ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \                # etcd 접속 주소
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \          # CA 인증서
  --cert=/etc/kubernetes/pki/etcd/server.crt \        # 클라이언트 인증서
  --key=/etc/kubernetes/pki/etcd/server.key \         # 클라이언트 키
  snapshot save /tmp/etcd-backup                      # 저장할 스냅샷 파일 경로
```

```
Snapshot saved at /tmp/etcd-backup
```

> `ETCDCTL_API=3`: etcdctl이 v3 API를 쓰도록 하는 환경변수. (최신 버전은 기본이 v3라 생략 가능하지만
> 습관적으로 붙이는 경우가 많습니다.)

백업 파일 상태 확인:

```bash
sudo ETCDCTL_API=3 etcdctl snapshot status /tmp/etcd-backup --write-out=table
```

## 3. 복구

복구는 스냅샷을 **새 데이터 디렉토리**에 풀어낸 뒤, etcd가 그 디렉토리를 바라보게 바꾸는
2단계로 진행합니다.

### 3-1. 스냅샷을 새 디렉토리로 복원

```bash
sudo ETCDCTL_API=3 etcdctl \
  --data-dir /var/lib/etcd-new \        # 기존(/var/lib/etcd)이 아닌 새 경로로!
  snapshot restore /tmp/etcd-backup
```

### 3-2. etcd가 새 디렉토리를 쓰도록 변경

etcd는 **static Pod**로 돌고 있어서, 매니페스트 파일(`/etc/kubernetes/manifests/etcd.yaml`)을
수정하면 kubelet이 자동으로 재시작합니다.

```bash
sudo vi /etc/kubernetes/manifests/etcd.yaml
```

`volumes` 섹션에서 etcd-data의 hostPath를 새 경로로 변경:

```yaml
  - hostPath:
      path: /var/lib/etcd-new     # ← /var/lib/etcd 에서 변경
      type: DirectoryOrCreate
    name: etcd-data
```

저장하면 잠시 후 etcd Pod가 새 데이터 디렉토리로 재시작되고, 클러스터가 백업 시점의 상태로
돌아옵니다. (`kubectl get pod -n kube-system` 으로 etcd Pod가 Running인지 확인)

> **주의**: 복구는 클러스터 전체에 영향을 주는 작업입니다. 운영 클러스터에서는 반드시 절차를
> 숙지하고, 연습용 클러스터에서 먼저 충분히 연습하세요. 복구 직후에는 API 서버 등 컨트롤 플레인
> 구성 요소가 재시작되느라 kubectl이 잠시 안 될 수 있습니다.

## 4. 간단 연습 시나리오

```bash
# 1) 백업
sudo ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  snapshot save /tmp/etcd-backup

# 2) 백업 이후 변경 사항 만들기
kubectl create deployment after-backup --image=nginx

# 3) 복구 (위 3-1, 3-2 절차)

# 4) 확인: after-backup Deployment가 사라져 있음 = 백업 시점으로 돌아감
kubectl get deploy
```

## 확인 문제

1. etcd에는 무엇이 저장되는가?
2. 복구할 때 기존 데이터 디렉토리가 아닌 새 디렉토리를 쓰는 이유는?
3. etcd 매니페스트 파일을 수정하면 재시작은 누가 해 주는가?

<details><summary>정답 보기</summary>

1. 클러스터의 모든 리소스 정의와 상태 (Pod, Deployment, Secret, ConfigMap 등 전부)
2. 기존 디렉토리(손상되었을 수 있는 현재 상태)를 보존하고, 깨끗한 위치에 복원본을 만들어 전환하기 위해
3. kubelet — static Pod는 `/etc/kubernetes/manifests/`의 파일 변경을 kubelet이 감지해 자동으로 재시작한다
</details>

---

🎉 수고하셨습니다! 전체 과정을 마쳤습니다. [cheatsheet.md](cheatsheet.md)를 옆에 두고
직접 이것저것 만들어 보는 것이 가장 좋은 복습입니다.
