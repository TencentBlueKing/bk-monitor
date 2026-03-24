#!/usr/bin/env python3
"""
UDP 回显服务 - 用于 UDP 拨测测试的简易被测服务。

监听指定端口，收到 UDP 包后原样回显（可选），便于验证拨测连通性与往返时延。
用法:
  python scripts/udp_echo_server.py [--port 9999] [--no-reply]
"""

from __future__ import annotations

import argparse
import socket
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="UDP 回显服务，用于拨测测试")
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=9999,
        help="监听端口 (默认: 9999)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址 (默认: 0.0.0.0)",
    )
    parser.add_argument(
        "--no-reply",
        action="store_true",
        help="只收包不回复（纯监听，拨测仅检测端口可达）",
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((args.host, args.port))
    except OSError as e:
        print(f"绑定失败 {args.host}:{args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"UDP 服务已启动: {args.host}:{args.port} (回显: {not args.no_reply})", flush=True)
    while True:
        data, addr = sock.recvfrom(65535)
        if not data:
            continue

        # 不回复
        if not args.no_reply:
            sock.sendto(data, addr)

        # 尝试解析为文本
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = "binary"

        print(f"收到 {addr}: {len(data)} 字节, {text}", flush=True)


if __name__ == "__main__":
    main()
