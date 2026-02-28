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

    sess = sub.add_parser("session")
    sess_sub = sess.add_subparsers(dest="session_cmd", required=True)
    upd = sess_sub.add_parser("update")
    upd.add_argument("--mode", choices=["latest", "stable"], default="latest")
    upd.add_argument("--stable-ms", type=int, default=650)
    upd.add_argument("--max-wait-ms", type=int, default=9000)
    upd.add_argument("--stable-warmup-ms", type=int, default=2000)
    upd.add_argument("--include-frames", action="store_true")
    upd.add_argument("--frame-limit", type=int, default=20)
    upd.add_argument("--include-char-stream", action="store_true")
    upd.add_argument("--char-limit", type=int, default=8000)
    hist = sess_sub.add_parser("history")
    hist.add_argument("--limit", type=int, default=50)
    hist.add_argument("--from-rev", type=int)
    hist.add_argument("--to-rev", type=int)
    hist.add_argument("--include-char-stream", action="store_true")
    hist.add_argument("--char-limit", type=int, default=8000)

    s = sub.add_parser("send")
    s.add_argument("--key")
    s.add_argument("--actions")
    s.add_argument("--stable-ms", type=int, default=650)
    s.add_argument("--max-wait-ms", type=int, default=9000)
    s.add_argument("--stable-warmup-ms", type=int, default=2000)

    # Agent-friendly wrappers around the daemon contract.
    sub.add_parser("screen")
    k = sub.add_parser("key")
    k.add_argument("key")
    t = sub.add_parser("type")
    t.add_argument("text")

    args = parser.parse_args()

    if args.command == "connect":
        payload = {
            "cmd": "connect",
            "host": args.host,
            "port": args.port,
            "width": args.width,
            "height": args.height,
        }
    elif args.command == "session" and args.session_cmd == "update":
        payload = {
            "cmd": "session_update",
            "mode": args.mode,
            "stable_ms": args.stable_ms,
            "max_wait_ms": args.max_wait_ms,
            "stable_warmup_ms": args.stable_warmup_ms,
            "include_frames": args.include_frames,
            "frame_limit": args.frame_limit,
            "include_char_stream": args.include_char_stream,
            "char_limit": args.char_limit,
        }
    elif args.command == "session" and args.session_cmd == "history":
        payload = {
            "cmd": "session_history",
            "limit": args.limit,
            "from_rev": args.from_rev,
            "to_rev": args.to_rev,
            "include_char_stream": args.include_char_stream,
            "char_limit": args.char_limit,
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
    elif args.command == "screen":
        payload = {
            "cmd": "session_update",
            "mode": "latest",
        }
    elif args.command == "key":
        payload = {
            "cmd": "send",
            "key": args.key,
        }
    elif args.command == "type":
        payload = {
            "cmd": "send",
            "actions": [{"k": "type", "text": args.text}],
        }
    else:
        raise RuntimeError("unsupported command")

    resp = daemon_request(payload, verbose=args.verbose)
    print_json(resp)
