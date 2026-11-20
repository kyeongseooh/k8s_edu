FROM python:3.12-alpine
WORKDIR /app
COPY report.py /app/report.py
USER 65532:65532
ENTRYPOINT ["python", "-I", "/app/report.py"]
