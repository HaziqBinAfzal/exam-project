import argparse
import hashlib
from pathlib import Path


def evidence_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Check a Scope 2 evidence file")
    parser.add_argument("file", type=Path)
    parser.add_argument("--expected", help="SHA-256 recorded when the evidence was issued")
    args = parser.parse_args()
    actual = evidence_hash(args.file)

    if args.expected is None:
        print(actual)
        return 0

    if actual == args.expected:
        print("VERIFIED: evidence matches the recorded hash")
        return 0

    print("MISMATCH: evidence differs from the recorded hash")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
