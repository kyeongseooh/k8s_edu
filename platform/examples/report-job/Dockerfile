FROM python:3.12-alpine
WORKDIR /app
COPY report.py .
USER 65534
# ENTRYPOINT는 고정된 실행 파일, 뒤에 붙는 인자(--amounts ...)는 실행할 때 바꿀 수 있다
ENTRYPOINT ["python", "report.py"]
