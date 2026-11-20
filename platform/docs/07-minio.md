# 07. MinIO — 브라우저에서는 보이는데 S3 작업은 왜 실패할까?

같은 데이터를 두 가지 입구에서 본다. **Console**은 사람이 로그인하는 웹 UI, **S3 API**는 AWS CLI·boto3·Kubeflow가 서명된 요청을 보내는 엔드포인트다. 이 환경에서 제공된 콘솔과 S3 API는 실제로 **서로 다른 포트**였다. 웹 페이지가 HTTP 200이라는 사실만으로 S3 엔드포인트라고 판단하지 않는다. 플랫폼 관리자에게 Console URL과 **S3 endpoint URL**을 별도로 받는다.

## 관리자 준비 · 사용자 권한

운영 버킷을 실습에 재사용하지 않는다. 플랫폼 관리자는 전용 private 버킷과 사용자별 prefix를 지급한다. 다음 정책의 `training-data`와 `students/team-a`는 예시 **고정값**이다. 실제 지급 경로와 동일하게 바꾼 후 제한된 사용자/STS 세션에 적용한다. `ListBucket`은 버킷에, 객체 GET/PUT/DELETE는 **객체 ARN**에 건다. `ListAllMyBuckets`, 버킷 삭제, 다른 prefix 권한은 필요 없다.

```json
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["s3:ListBucket"],"Resource":["arn:aws:s3:::training-data"],"Condition":{"StringLike":{"s3:prefix":["students/team-a/*"]}}},
  {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject"],"Resource":["arn:aws:s3:::training-data/students/team-a/*"]}
]}
```

## 실습 — 같은 객체를 올리고 검증하기

AWS CLI v2, 검증 가능한 TLS 또는 관리자가 승인한 보호된 접속 경로를 사용한다. 사용자에게는 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, (STS인 경우) `AWS_SESSION_TOKEN`을 별도 비밀 전달 경로로 지급한다. 셸 명령·Git·DAG·스크린샷에 실제 값을 넣지 않는다. 사용자가 서버 root 자격 증명이나 기존 Harbor/KFP artifact 버킷을 사용할 이유는 없다.

```bash
: "${S3_ENDPOINT:?S3 API 주소}" "${BUCKET:?개인 실습용 버킷}" "${PREFIX:?지급된 prefix 예 students/team-a}"
W=$(mktemp -d); KEY="${PREFIX%/}/hello-$(date +%s)-${RANDOM}.txt"
s3() { aws --endpoint-url "$S3_ENDPOINT" --region us-east-1 s3api "$@"; }
printf 'platform class\n' > "$W/input"
s3 put-object --bucket "$BUCKET" --key "$KEY" --body "$W/input"
s3 get-object --bucket "$BUCKET" --key "$KEY" "$W/output"
sha256sum "$W/input" "$W/output"; cmp "$W/input" "$W/output"
```

Console에서 권한이 있는 경우 **Object Browser → 지급받은 버킷 → 동일한 key**를 찾는다. 제한 계정에서는 버킷 전체 목록을 보여주지 않을 수 있다. `ETag=파일의 MD5`로 단정하지 않는다. 멀티파트 업로드나 암호화에 따라 달라질 수 있어 위에서는 직접 내려받은 바이트로 검증했다.

**장애 과제:** 내 prefix 안에서 방금 업로드한 key의 파일명만 틀리게 요청한 뒤 올바른 key로 복구한다. 실제 객체/버킷을 삭제해서 장애를 만들 필요가 없다.

```bash
rc=0; s3 get-object --bucket "$BUCKET" --key "${KEY}.typo" "$W/missing" || rc=$?
printf '오타 요청 exit=%s (nonzero 기대)\n' "$rc"
s3 get-object --bucket "$BUCKET" --key "$KEY" "$W/recovered" && cmp "$W/input" "$W/recovered"
```

| 증상 | 먼저 구분할 것 |
|---|---|
| HTML 응답·리다이렉트·파싱 실패 | S3 API 대신 Console URL을 넣었는가? |
| `AccessDenied`/403 | 세션 만료, 작업 동사와 prefix 정책, 잘못된 버킷. 목록 권한이 없으면 없는 key도 403일 수 있다. |
| `NoSuchKey`/404 | 버킷·대소문자·prefix 포함 전체 key가 맞는가? |
| `SignatureDoesNotMatch` | 시크릿·리전·시계·프록시가 바꾼 Host를 확인한다. |

정리: `s3 delete-object --bucket "$BUCKET" --key "$KEY"`로 **이번에 만든 key 하나만** 지운다. 버전 관리 버킷이면 삭제 마커와 실제 버전 삭제는 다르므로 관리자 보존 정책을 따른다. 실습용 세션을 종료하고 임시 디렉터리를 정리한다. 재귀 버킷 삭제는 하지 않는다.
