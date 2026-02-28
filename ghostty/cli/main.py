import argparse
import json

from .client import daemon_request


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="ghostty")
    parser.add_argument("--verbose", action="store_true", help="Enable daemon log redirection to file")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("connect")
    c.add_argument("host")
    c.add_argument("--port", type=int, default=23)
    c.add_argument("--width", type=int, default=80)
    c.add_argument("--height", type=int, default=24)
    c.add_argument("--io-log-path")

    sess = sub.add_parser("session")
    sess_sub = sess.add_subparsers(dest="session_cmd", required=True)
    upd = sess_sub.add_parser("update")
    upd.add_argument("--mode", choices=["latest", "stable"], default="latest")
    upd.add_argument("--stable-ms", type=int, default=650)
    upd.add_argument("--max-wait-ms", type=int, default=9000)
    upd.add_argument("--stable-warmup-ms", type=int, default=2000)

    s = sub.add_parser("send")
    s.add_argument("--key")
    s.add_argument("--actions")
    s.add_argument("--stable-ms", type=int, default=650)
    s.add_argument("--max-wait-ms", type=int, default=9000)
    s.add_argument("--stable-warmup-ms", type=int, default=2000)

    args = parser.parse_args()

    if args.command == "connect":
        payload = {
            "cmd": "connect",
            "host": args.host,
            "port": args.port,
            "width": args.width,
            "height": args.height,
            "io_log_path": args.io_log_path,
        }
    elif args.command == "session" and args.session_cmd == "update":
        payload = {
            "cmd": "session_update",
            "mode": args.mode,
            "stable_ms": args.stable_ms,
            "max_wait_ms": args.max_wait_ms,
            "stable_warmup_ms": args.stable_warmup_ms,
        }
    elif args.command == "send":
        payload = {
            "cmd": "send",
            "stable_ms": args.stable_ms,
            "max_wait_ms": args.max_wait_ms,
            "stable_warmup_ms": args.stable_warmup_ms,
        }
        if args.key:
            payload["key"] = args.key
        if args.actions:
            payload["actions"] = json.loads(args.actions)
    else:
        raise RuntimeError("unsupported command")

    resp = daemon_request(payload, verbose=args.verbose)
    print_json(resp)
