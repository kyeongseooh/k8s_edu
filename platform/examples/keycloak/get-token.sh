#!/bin/bash
# Keycloak에 사용자 이름과 비밀번호로 로그인해서 ID 토큰을 받아 출력한다.
# 사용법: ./get-token.sh <사용자 이름>      (비밀번호는 물어본다)
set -euo pipefail
ISSUER=https://sso.10.0.1.230.nip.io/realms/edu-k8s
CA=${OIDC_CA:-/root/edu-oidc/ca.crt}
USERNAME=${1:?사용자 이름을 입력하세요}
read -rs -p "Password for $USERNAME: " PASSWORD; echo >&2
curl -s --cacert "$CA" "$ISSUER/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=kubernetes -d scope=openid \
  -d "username=$USERNAME" --data-urlencode "password=$PASSWORD" |
  jq -r 'if .id_token then .id_token else ("로그인 실패: " + (.error_description // .error // "unknown")) | halt_error(1) end'
