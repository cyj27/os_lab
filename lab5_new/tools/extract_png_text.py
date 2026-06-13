#!/usr/bin/env python3
"""Extract tEXt/zTXt chunks from a PNG file."""

from __future__ import annotations

import argparse
import zlib
from pathlib import Path


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def extract(path: Path) -> None:
    data = path.read_bytes()
    if not data.startswith(PNG_MAGIC):
        raise SystemExit(f"not a PNG file: {path}")

    pos = len(PNG_MAGIC)
    while pos + 12 <= len(data):
        size = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + size]
        pos += 12 + size
        if len(payload) != size:
            raise SystemExit("truncated PNG chunk")

        if kind == b"tEXt" and b"\x00" in payload:
            keyword, text = payload.split(b"\x00", 1)
            print(f"[{keyword.decode(errors='replace')}]")
            print(text.decode("utf-8", errors="replace"))
        elif kind == b"zTXt" and b"\x00" in payload:
            keyword, rest = payload.split(b"\x00", 1)
            if rest[:1] != b"\x00":
                continue
            print(f"[{keyword.decode(errors='replace')}]")
            print(zlib.decompress(rest[1:]).decode("utf-8", errors="replace"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PNG text chunks.")
    parser.add_argument("png", type=Path)
    args = parser.parse_args()
    extract(args.png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
