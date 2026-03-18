from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Optional, TextIO, Tuple

JSONScalar = None | bool | int | float | str
JSONObject = dict[str, "JSONValue"]
JSONArray = list["JSONValue"]
JSONValue = JSONScalar | JSONObject | JSONArray


@dataclass(frozen=True)
class DecodedDatagram:
    text: str
    json_obj: JSONValue | None = None


def decode_datagram(data: bytes, encoding: str = "utf-8") -> DecodedDatagram:
    text = data.decode(encoding, errors="replace").strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
            return DecodedDatagram(text=text, json_obj=obj)
        return DecodedDatagram(text=text, json_obj=None)
    except Exception:
        return DecodedDatagram(text=text, json_obj=None)


def listen_once(
    host: str,
    port: int,
    *,
    timeout_s: float = 1.0,
    bufsize: int = 65535,
    encoding: str = "utf-8",
) -> Tuple[DecodedDatagram, Tuple[str, int]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, port))
        sock.settimeout(timeout_s)
        data, addr = sock.recvfrom(bufsize)
        return decode_datagram(data, encoding=encoding), addr
    finally:
        sock.close()


def _fmt_float(x: Any) -> str:
    try:
        return f"{float(x): .3f}".strip()
    except Exception:
        return str(x)


def summarize_json(obj: Any, max_items: int = 12) -> str:
    if not isinstance(obj, Mapping):
        s = str(obj)
        return s if len(s) <= 200 else s[:197] + "..."

    parts: list[str] = []

    axes = obj.get("axes")
    if isinstance(axes, Sequence) and not isinstance(axes, (str, bytes, bytearray)):
        axes_list = list(axes)
        shown = " ".join(_fmt_float(v) for v in axes_list[:max_items])
        tail = "" if len(axes_list) <= max_items else f" …(+{len(axes_list) - max_items})"
        parts.append(f"axes[{len(axes_list)}]: {shown}{tail}")

    buttons = obj.get("buttons")
    if isinstance(buttons, Sequence) and not isinstance(buttons, (str, bytes, bytearray)):
        buttons_list = list(buttons)
        pressed = [str(i) for i, v in enumerate(buttons_list) if bool(v)]
        if pressed:
            parts.append(
                f"btn: {','.join(pressed[:max_items])}" + ("" if len(pressed) <= max_items else "…")
            )
        else:
            parts.append("btn: -")

    hats = obj.get("hats") if "hats" in obj else obj.get("hat")
    if isinstance(hats, Sequence) and not isinstance(hats, (str, bytes, bytearray)):
        hats_list = list(hats)
        parts.append(f"hat: {hats_list[:max_items]}" + ("" if len(hats_list) <= max_items else "…"))
    elif hats is not None:
        parts.append(f"hat: {hats}")

    extras = [str(k) for k in obj.keys() if str(k) not in {"axes", "buttons", "hats", "hat"}]
    if extras:
        ex = ",".join(extras[:6])
        parts.append(f"extra: {ex}" + ("" if len(extras) <= 6 else "…"))

    line = " | ".join(parts) if parts else str(dict(obj))
    return line if len(line) <= 260 else line[:257] + "..."


class LiveLinePrinter:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self._last_len = 0

    def write(self, line: str) -> None:
        pad = max(0, self._last_len - len(line))
        self.stream.write("\r" + line + (" " * pad))
        self.stream.flush()
        self._last_len = len(line)

    def finish(self) -> None:
        self.stream.write("\n")
        self.stream.flush()
        self._last_len = 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Listen on a UDP port and print received datagrams.")
    p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=50100, help="UDP port to bind (default: 50100)")
    p.add_argument("--max", type=int, default=0, help="Stop after N packets (0 = infinite)")
    p.add_argument(
        "--timeout", type=float, default=0.0, help="Socket timeout in seconds (0 = none)"
    )
    p.add_argument("--encoding", default="utf-8", help="Payload decoding (default: utf-8)")
    p.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON payloads (scrolling mode)"
    )
    p.add_argument(
        "--compact", action="store_true", help="Compact one-line output (scrolling mode)"
    )
    p.add_argument(
        "--live", action="store_true", help="Live one-line output (overwrite previous line)"
    )
    p.add_argument(
        "--rate", type=float, default=30.0, help="Max live refresh rate in Hz (default: 30)"
    )

    args = p.parse_args(argv)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((args.host, args.port))
        if args.timeout and args.timeout > 0:
            sock.settimeout(args.timeout)

        print(f"listening on {args.host}:{args.port} ...", file=sys.stderr)

        live_printer = LiveLinePrinter(sys.stdout)
        next_emit_t = 0.0
        emit_dt = 0.0 if args.rate <= 0 else (1.0 / args.rate)

        count = 0
        while True:
            data, addr = sock.recvfrom(65535)
            dd = decode_datagram(data, encoding=args.encoding)

            if args.live:
                now = time.perf_counter()
                if now < next_emit_t:
                    continue
                next_emit_t = now + emit_dt

                if dd.json_obj is not None:
                    s = summarize_json(dd.json_obj)
                else:
                    s = dd.text
                    if len(s) > 260:
                        s = s[:257] + "..."
                line = f"{addr[0]}:{addr[1]} | {s}"
                live_printer.write(line)
            else:
                if dd.json_obj is not None and args.pretty:
                    print(json.dumps(dd.json_obj, indent=2, ensure_ascii=False))
                elif dd.json_obj is not None and args.compact:
                    print(summarize_json(dd.json_obj))
                else:
                    print(dd.text)

            count += 1
            if args.max and count >= args.max:
                break

        if args.live:
            live_printer.finish()
        return 0

    except KeyboardInterrupt:
        if args.live:
            LiveLinePrinter(sys.stdout).finish()
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
