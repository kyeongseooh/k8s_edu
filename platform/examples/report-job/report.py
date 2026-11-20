"""숫자 목록을 받아 합계를 출력하고 끝나는 배치 작업.

사용법: python report.py --amounts 10,20,12
잘못된 값이 들어오면 종료 코드 2로 끝난다 (실패를 실패로 알리기 위해).
"""
import argparse
import socket
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--amounts", default="10,20,12")
    args = parser.parse_args()
    print(f"report: start on {socket.gethostname()} amounts={args.amounts}", flush=True)
    try:
        amounts = [int(x) for x in args.amounts.split(",")]
    except ValueError as exc:
        print(f"report: ERROR bad input: {exc}", file=sys.stderr, flush=True)
        return 2
    print(f"report_ok rows={len(amounts)} total={sum(amounts)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
