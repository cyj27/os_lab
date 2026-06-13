#!/usr/bin/env python3
"""Shared payload generation for the repair-fs lab.

The payload is deterministic for (student_id, LAB_SECRET).  The secret must be
kept by instructors; students should only see the generated disk image.
"""

from __future__ import annotations

import argparse
import binascii
import gzip
import hashlib
import hmac
import json
import os
import re
import struct
import zipfile
import zlib
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable


STAGES = ("ext2", "fat32", "ntfs")


def validate_student_id(student_id: str) -> str:
    if not re.fullmatch(r"\d{12}", student_id):
        raise ValueError("student id must be exactly 12 decimal digits")
    return student_id


def token(secret: str, student_id: str, label: str, n: int = 24) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"repair-fs:{student_id}:{label}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:n].upper()


def flag(secret: str, student_id: str, stage: str) -> str:
    return f"{stage.upper()}{{{token(secret, student_id, stage)}}}"


def deterministic_bytes(secret: str, student_id: str, label: str, size: int) -> bytes:
    """Return stable pseudo-random bytes for filesystem churn files."""
    out = bytearray()
    counter = 0
    while len(out) < size:
        out.extend(
            hmac.new(
                secret.encode("utf-8"),
                f"repair-fs:{student_id}:noise:{label}:{counter}".encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        counter += 1
    return bytes(out[:size])


def deterministic_text(secret: str, student_id: str, label: str, size: int) -> bytes:
    header = (
        f"repair-fs generated file\n"
        f"student_id={student_id}\n"
        f"label={label}\n\n"
    ).encode("utf-8")
    alphabet = deterministic_bytes(secret, student_id, label, max(size, 64)).hex().encode("ascii")
    body = (header + alphabet + b"\n") * ((size // (len(header) + len(alphabet) + 1)) + 2)
    return body[:size]


def build_zip(entries: Dict[str, bytes]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 4, 30, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return buf.getvalue()


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def build_png_with_note(note: bytes) -> bytes:
    width, height = 96, 64
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            stripe = ((x // 8) + (y // 8)) % 2
            if stripe:
                row.extend((0x2F, 0x76, 0x9B))
            else:
                row.extend((0xE8, 0xF1, 0xF5))
        rows.append(bytes(row))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ztxt = b"repair-fs\x00\x00" + zlib.compress(note, level=9)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", ihdr),
            png_chunk(b"zTXt", ztxt),
            png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9)),
            png_chunk(b"IEND", b""),
        ]
    )


def payload_files(student_id: str, secret: str) -> Dict[str, Dict[str, bytes | str]]:
    validate_student_id(student_id)
    suffix = token(secret, student_id, "suffix", 8).lower()

    ext2_flag = flag(secret, student_id, "ext2")
    fat_flag = flag(secret, student_id, "fat32")
    ntfs_flag = flag(secret, student_id, "ntfs")

    ext2_target = f"case_ext2/rescue_{suffix}.log.gz"
    fat_target = f"LOST{suffix[:4].upper()}.ZIP"
    ntfs_target = f"Users/ops/Desktop/incident_{suffix}.png"

    ext2_text = f"""OS lab: repair-fs ext2 incident log
student_id={student_id}
case=stage-1-ext2
flag={ext2_flag}

The inode still remembers more than the directory admits. :)
Read metadata first, recover data second, and write recovered files elsewhere.
""".encode("utf-8")

    fat_text = f"""OS lab: repair-fs FAT32 archive note
student_id={student_id}
case=stage-2-fat32
flag={fat_flag}

The directory entry lost its first byte, but the file content did not. (*^o^*)
Check the cluster chain and verify the result by hash, not by filename alone.
""".encode("utf-8")

    ntfs_text = f"""OS lab: repair-fs NTFS image note
student_id={student_id}
case=stage-3-ntfs
flag={ntfs_flag}

The useful clue is usually in file records and attributes before it is in data. ;)
The flag is stored in a compressed PNG text chunk named repair-fs.
""".encode("utf-8")

    ext2_body = gzip.compress(ext2_text, compresslevel=9, mtime=0)
    fat_body = build_zip(
        {
            "README.txt": b"Recovered FAT32 evidence archive.\n",
            "field-note.txt": fat_text,
        }
    )
    ntfs_body = build_png_with_note(ntfs_text)

    return {
        "ext2": {
            "target": ext2_target,
            "content": ext2_body,
            "hint": f"rescue_{suffix}.log.gz",
        },
        "fat32": {
            "target": fat_target,
            "content": fat_body,
            "hint": f"?OST{suffix[:4].upper()}.ZIP",
        },
        "ntfs": {
            "target": ntfs_target,
            "content": ntfs_body,
            "hint": f"incident_{suffix}.png",
        },
    }


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def answer_key(student_id: str, secret: str) -> Dict[str, object]:
    files = payload_files(student_id, secret)
    stages = {}
    for stage, meta in files.items():
        content = meta["content"]
        assert isinstance(content, bytes)
        stage_flag = flag(secret, student_id, stage)
        stages[stage] = {
            "flag": stage_flag,
            "flag_sha256": sha256(stage_flag.encode("utf-8")),
            "sha256": sha256(content),
            "target": meta["target"],
            "hint": meta["hint"],
            "size": len(content),
        }
    return {
        "student_id": student_id,
        "format": "repair-fs-answer-key-v1",
        "stages": stages,
    }


def write_file(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


def materialize_payload(out_dir: Path, student_id: str, secret: str) -> Dict[str, object]:
    files = payload_files(student_id, secret)
    if out_dir.exists():
        raise FileExistsError(f"output directory already exists: {out_dir}")
    out_dir.mkdir(parents=True)

    # ext2 tree
    write_file(
        out_dir / "ext2" / "README.txt",
        "Stage 1 visible note: recover the deleted rescue log from this ext2 volume.\n"
        "The volume also contains normal project files and stale deleted inodes.\n",
    )
    write_file(out_dir / "ext2" / str(files["ext2"]["target"]), files["ext2"]["content"])
    write_file(
        out_dir / "ext2" / "case_ext2" / "timeline.txt",
        "16:42 rotate debug traces\n17:03 rebuild cache files\n17:09 delete rescue log\n",
    )
    write_file(
        out_dir / "ext2" / "case_ext2" / "inventory.txt",
        deterministic_text(secret, student_id, "ext2-live-inventory", 2048),
    )
    write_file(
        out_dir / "ext2" / "case_ext2" / "snapshots" / "daily.bin",
        deterministic_bytes(secret, student_id, "ext2-live-daily", 12288),
    )

    # FAT32 tree
    write_file(
        out_dir / "fat32" / "CASE2.TXT",
        f"Stage 2 visible note: a deleted 8.3 file looks like {files['fat32']['hint']}.\n"
        "Expect other deleted entries from normal removable-drive activity.\n",
    )
    write_file(out_dir / "fat32" / str(files["fat32"]["target"]), files["fat32"]["content"])
    write_file(out_dir / "fat32" / "DECOY.TXT", "This is not the lost field note.\n")
    write_file(
        out_dir / "fat32" / "README2.TXT",
        deterministic_text(secret, student_id, "fat32-live-readme2", 1536),
    )

    # NTFS tree
    write_file(
        out_dir / "ntfs" / "README.txt",
        "Stage 3 visible note: inspect NTFS file records before trusting names.\n"
        "Several unrelated files were edited and removed before the incident image disappeared.\n",
    )
    write_file(out_dir / "ntfs" / str(files["ntfs"]["target"]), files["ntfs"]["content"])
    write_file(out_dir / "ntfs" / "Users" / "ops" / "Desktop" / "todo.txt", "verify recovered report\n")
    write_file(
        out_dir / "ntfs" / "ProgramData" / "ops-cache" / "index.dat",
        deterministic_bytes(secret, student_id, "ntfs-live-index", 24576),
    )

    # Churn files are not part of the final visible payload tree.  The disk
    # builder writes, deletes, replaces, or renames them to leave realistic
    # allocation history before the target evidence is finally deleted.
    churn_specs = {
        "ext2": [
            ("alpha.tmp", "ext2-churn-alpha", 377),
            ("beta.tmp", "ext2-churn-beta", 4096),
            ("gamma.tmp", "ext2-churn-gamma", 13333),
            ("delta.tmp", "ext2-churn-delta", 65536),
            ("report.v1", "ext2-churn-report-v1", 2304),
            ("report.v2", "ext2-churn-report-v2", 8192),
        ],
        "fat32": [
            ("A0001.TMP", "fat32-churn-a0001", 512),
            ("BULK1.BIN", "fat32-churn-bulk1", 7000),
            ("BULK2.BIN", "fat32-churn-bulk2", 28672),
            ("EDITOLD.TXT", "fat32-churn-edit-old", 900),
            ("EDITNEW.TXT", "fat32-churn-edit-new", 5000),
        ],
        "ntfs": [
            ("trace-small.bin", "ntfs-churn-trace-small", 600),
            ("trace-medium.bin", "ntfs-churn-trace-medium", 16384),
            ("trace-large.bin", "ntfs-churn-trace-large", 98304),
            ("notes-v1.txt", "ntfs-churn-notes-v1", 1200),
            ("notes-v2.txt", "ntfs-churn-notes-v2", 7400),
        ],
    }
    for fs_name, specs in churn_specs.items():
        for filename, label, size in specs:
            data = (
                deterministic_text(secret, student_id, label, size)
                if filename.lower().endswith(".txt") or "." not in filename
                else deterministic_bytes(secret, student_id, label, size)
            )
            write_file(out_dir / "churn" / fs_name / filename, data)

    key = answer_key(student_id, secret)
    (out_dir / "answer-key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return key


def secret_from_args(args: argparse.Namespace) -> str:
    if args.secret:
        return args.secret
    if os.environ.get("LAB_SECRET"):
        return os.environ["LAB_SECRET"]
    if args.demo:
        return "INSECURE-DEMO-SECRET-DO-NOT-USE-FOR-CLASS"
    raise SystemExit("missing secret: pass --secret, set LAB_SECRET, or use --demo for local testing")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate per-student repair-fs lab payload files.")
    parser.add_argument("--student-id", required=True, help="12 digit student id")
    parser.add_argument("--out-dir", required=True, type=Path, help="new directory to create")
    parser.add_argument("--secret", help="instructor secret; prefer LAB_SECRET environment variable")
    parser.add_argument("--demo", action="store_true", help="use an insecure deterministic demo secret")
    parser.add_argument("--print-answer-key", action="store_true", help="print answer key JSON to stdout")
    args = parser.parse_args(list(argv) if argv is not None else None)

    student_id = validate_student_id(args.student_id)
    secret = secret_from_args(args)
    key = materialize_payload(args.out_dir, student_id, secret)
    if args.print_answer_key:
        print(json.dumps(key, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
