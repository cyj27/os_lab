#!/usr/bin/env python3
"""Grade a repair-fs lab submission.

The grader intentionally checks only evidence that depends on the instructor
secret.  It does not need the original image.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import zipfile
import zlib
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from payload import answer_key, secret_from_args, validate_student_id  # noqa: E402


MAX_TEXT_BYTES = 4 * 1024 * 1024


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path


def decode_text(data: bytes) -> str:
    if len(data) > MAX_TEXT_BYTES:
        data = data[:MAX_TEXT_BYTES]
    return data.decode("utf-8", errors="ignore")


def png_text_chunks(data: bytes) -> List[str]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return []
    out = []
    pos = 8
    while pos + 12 <= len(data):
        size = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + size]
        pos += 12 + size
        if len(payload) != size:
            break
        if kind == b"tEXt" and b"\x00" in payload:
            _, text = payload.split(b"\x00", 1)
            out.append(decode_text(text))
        elif kind == b"zTXt" and b"\x00" in payload:
            _, rest = payload.split(b"\x00", 1)
            if rest[:1] == b"\x00":
                try:
                    out.append(decode_text(zlib.decompress(rest[1:])))
                except zlib.error:
                    pass
    return out


def searchable_texts_from_bytes(data: bytes) -> List[str]:
    texts = [decode_text(data)]
    try:
        texts.append(decode_text(gzip.decompress(data)))
    except (OSError, EOFError):
        pass
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            for name in zf.namelist():
                if not name.endswith("/"):
                    texts.extend(searchable_texts_from_bytes(zf.read(name)))
    except (zipfile.BadZipFile, RuntimeError, zlib.error):
        pass
    texts.extend(png_text_chunks(data))
    return texts


def read_searchable_text(path: Path) -> str:
    return "\n".join(searchable_texts_from_bytes(path.read_bytes()))


def load_public_manifest(path: Path, student_id: str) -> Dict[str, object]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("format") != "repair-fs-public-manifest-v1":
        raise ValueError(f"unsupported manifest format: {manifest.get('format')}")
    students = manifest.get("students", {})
    if student_id not in students:
        raise ValueError(f"student id not found in manifest: {student_id}")
    return {
        "student_id": student_id,
        "format": "repair-fs-public-answer-key-v1",
        "stages": students[student_id]["stages"],
    }


def expected_key(args: argparse.Namespace, student_id: str) -> Dict[str, object]:
    if args.answer_key:
        key = json.loads(args.answer_key.read_text(encoding="utf-8"))
        if key.get("format") != "repair-fs-answer-key-v1":
            raise ValueError(f"unsupported answer key format: {key.get('format')}")
        if key.get("student_id") != student_id:
            raise ValueError(
                f"answer key student id mismatch: expected {student_id}, got {key.get('student_id')}"
            )
        return key
    if args.manifest:
        return load_public_manifest(args.manifest, student_id)
    secret = secret_from_args(args)
    return answer_key(student_id, secret)


def flag_present(combined_text: str, expected: Dict[str, object]) -> bool:
    if "flag" in expected:
        return str(expected["flag"]) in combined_text
    expected_hash = expected.get("flag_sha256")
    if not expected_hash:
        raise ValueError("expected stage entry has neither flag nor flag_sha256")
    candidates = re.findall(r"(?:EXT2|FAT32|NTFS)\{[0-9A-Fa-f]{24}\}", combined_text)
    candidates.extend(word.strip() for word in combined_text.replace("\r", "\n").split())
    for candidate in candidates:
        if hashlib.sha256(candidate.encode("utf-8")).hexdigest() == expected_hash:
            return True
    return False


def grade(submission_dir: Path, key: Dict[str, object]) -> Dict[str, object]:
    files = list(iter_files(submission_dir))
    combined = "\n".join(read_searchable_text(path) for path in files)

    stages = {}
    total = 0
    for stage, expected in key["stages"].items():
        found = flag_present(combined, expected)
        stages[stage] = {
            "ok": found,
            "expected_flag_sha256": expected.get("flag_sha256"),
            "hint": expected["hint"],
        }
        total += 1 if found else 0

    return {
        "student_id": key["student_id"],
        "submission_dir": str(submission_dir),
        "score": total,
        "max_score": len(key["stages"]),
        "ok": total == len(key["stages"]),
        "stages": stages,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grade repair-fs lab flags.")
    parser.add_argument("--student-id", required=True, help="12 digit student id")
    parser.add_argument("--submission-dir", required=True, type=Path, help="directory containing the student's files")
    parser.add_argument("--secret", help="instructor secret; prefer LAB_SECRET environment variable")
    parser.add_argument("--demo", action="store_true", help="use the insecure demo secret")
    parser.add_argument("--manifest", type=Path, help="public manifest for student-side offline checking")
    parser.add_argument("--answer-key", type=Path, help="private answer-key JSON generated under dist/")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args(list(argv) if argv is not None else None)

    student_id = validate_student_id(args.student_id)
    key = expected_key(args, student_id)
    result = grade(args.submission_dir, key)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"student_id: {result['student_id']}")
        print(f"score: {result['score']}/{result['max_score']}")
        for stage, stage_result in result["stages"].items():
            status = "ok" if stage_result["ok"] else "missing"
            print(f"{stage}: {status}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
