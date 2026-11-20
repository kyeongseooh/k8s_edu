"""요청을 받으면 버전과 Pod 이름을 응답하는 아주 작은 웹 서버 (표준 라이브러리만 사용)."""
import os
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

VERSION = os.environ.get("APP_VERSION", "v1")
MESSAGE = os.environ.get("APP_MESSAGE", "Hello from Harbor")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"{MESSAGE} | version={VERSION} | host={socket.gethostname()}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):          # 요청 로그를 표준 출력으로 (kubectl logs 로 보인다)
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"hello-app {VERSION} listening on :8080", flush=True)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
