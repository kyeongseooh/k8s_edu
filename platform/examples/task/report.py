"""A tiny batch report; deterministic and safe to rerun. No external I/O."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--amounts', default='10,12,20')
    args = parser.parse_args()
    try:
        amounts = [int(value) for value in args.amounts.split(',')]
    except ValueError:
        parser.error('amounts must be comma-separated integers')
    print(f'report_ok rows={len(amounts)} total={sum(amounts)}', flush=True)


if __name__ == '__main__':
    main()
