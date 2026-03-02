# tools/sniff_udp.py
import argparse
import socket
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--decode", default="utf-8")
    ap.add_argument("--max", type=int, default=4096)
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(0.5)  # makes Ctrl+C reliable
    print(f"listening {(args.host, args.port)}  (Ctrl+C to stop)")
    sys.stdout.flush()

    count = 0
    try:
        while True:
            try:
                data, addr = sock.recvfrom(args.max)
            except socket.timeout:
                continue
            count += 1
            # Print a compact line
            try:
                s = data.decode(args.decode, "replace").strip()
            except Exception:
                s = repr(data)
            if len(s) > 300:
                s = s[:300] + " …"
            print(f"{count:06d} from {addr}: {s}")
    except KeyboardInterrupt:
        print("\nbye")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())