#!/bin/sh
# Pod 안에서 실행: 자기 ServiceAccount 토큰으로 쿠버네티스 API를 호출해 HTTP 상태 코드를 출력한다
# 사용법: sh api-call.sh pods   또는   sh api-call.sh secrets
SA_DIR=/var/run/secrets/kubernetes.io/serviceaccount
TOKEN=$(cat $SA_DIR/token)
NS=$(cat $SA_DIR/namespace)
curl -s -o /dev/null -w "$1: HTTP %{http_code}\n" \
  --cacert $SA_DIR/ca.crt -H "Authorization: Bearer $TOKEN" \
  https://kubernetes.default.svc/api/v1/namespaces/$NS/$1
