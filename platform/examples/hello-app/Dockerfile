# 1) 어떤 이미지 위에 쌓을지: 파이썬이 설치된 가벼운 리눅스
FROM python:3.12-alpine

# 2) 컨테이너 안의 작업 디렉터리
WORKDIR /app

# 3) 내 코드를 이미지 안으로 복사
COPY app.py .

# 4) 빌드할 때 버전을 넣을 수 있게 한다 (docker build --build-arg APP_VERSION=v2)
ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION}

# 5) root가 아닌 일반 사용자로 실행 (보안상 권장)
USER 65534

# 6) 이 컨테이너가 쓰는 포트 (설명용)
EXPOSE 8080

# 7) 컨테이너가 시작될 때 실행할 명령
CMD ["python", "app.py"]
