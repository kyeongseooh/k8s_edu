# 18. Job / CronJob — 매일 보고서가 한 번 끝나야 한다면

Deployment는 서버를 계속 **살려 두는** 용도다. **Job**은 작업의 성공적인 **종료**를 관리하고, **CronJob**은 일정에 따라 Job을 생성한다. CronJob → Job → Pod 순으로 내려가야 실패한 실행의 로그를 찾을 수 있다.

[야간 보고서 예제](../examples/18-batch/report.yaml)는 매일 UTC 02:15 일정이지만 `suspend: true`로 둔다. 수업 중에는 예약 시간까지 기다리는 대신 같은 템플릿으로 수동 Job을 만든다. `backoffLimit: 0`은 이번 실패를 숨기지 않고 바로 관찰하기 위한 교육용 값이다. `concurrencyPolicy: Forbid`는 **같은 CronJob이 예약 실행한** 이전 Job이 끝나지 않았다면 겹쳐 시작하지 않도록 한다. 수동 실행까지 막아주는 자물쇠나 정확히 한 번 실행된다는 보장은 아니다. 운영 배치는 같은 날짜를 재처리해도 결과가 중복되지 않게 설계한다.

## 과제: 배치 설정 오타로 오늘 보고서만 실패

```bash
k apply -f examples/18-batch/report.yaml
k create job report-baseline --from=cronjob/daily-report
k wait job/report-baseline --for=condition=Complete --timeout=150s
k logs job/report-baseline
```

정상 로그는 `report generated: daily`. 잘못된 입력을 템플릿에 넣고 **다른 이름**으로 실행한다. 웹 서버와 달리 `Running`이 목표가 아니다. Job 상태와 종료 코드를 함께 확인하자.

```bash
k set env cronjob/daily-report REPORT_MODE=daliy
k create job report-bad --from=cronjob/daily-report
k wait job/report-bad --for=condition=Failed --timeout=150s
k logs job/report-bad
k get pod -l job-name=report-bad -o jsonpath='{.items[0].status.containerStatuses[0].state.terminated.exitCode}{"\n"}'
```

<details><summary>힌트와 복구</summary>

종료 코드 `2`와 `unknown report mode: daliy`는 입력 검증 실패다. 옛 Job은 이미 만든 실행 기록이라 CronJob 수정을 소급 적용받지 않는다. 템플릿의 오타를 고치고 새 실행을 만든다.

```bash
k set env cronjob/daily-report REPORT_MODE=daily
k create job report-retry --from=cronjob/daily-report
k wait job/report-retry --for=condition=Complete --timeout=150s
k logs job/report-retry
k get jobs report-baseline report-bad report-retry
```

성공 기준: 실패 기록은 보존된 채 `report-retry`만 새로 성공하고 정상 보고서 로그가 나온다.
</details>

```bash
k delete job report-baseline report-bad report-retry
k delete -f examples/18-batch/report.yaml
```

복습: [증상별 치트시트](cheatsheet.md) · [전체 목차](../README.md)
