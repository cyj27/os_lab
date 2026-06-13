#!/usr/bin/env python3
"""Create a public self-check manifest without exposing LAB_SECRET or flags."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

from payload import answer_key, secret_from_args, validate_student_id


def read_student_ids(args: argparse.Namespace) -> List[str]:
    ids = list(args.student_id or [])
    if args.student_ids_file:
        for line in args.student_ids_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                ids.append(line)
    if not ids:
        raise SystemExit("provide --student-id at least once or --student-ids-file")
    return [validate_student_id(student_id) for student_id in ids]


def public_entry(student_id: str, secret: str) -> dict:
    private_key = answer_key(student_id, secret)
    stages = {}
    for stage, expected in private_key["stages"].items():
        stages[stage] = {
            "flag_sha256": expected["flag_sha256"],
            "hint": expected["hint"],
            "target": expected["target"],
            "size": expected["size"],
        }
    return {"stages": stages}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build public repair-fs self-check manifest.")
    parser.add_argument("--student-id", action="append", help="12 digit student id; may be repeated")
    parser.add_argument("--student-ids-file", type=Path, help="text file containing one student id per line")
    parser.add_argument("--out", required=True, type=Path, help="manifest JSON path to write")
    parser.add_argument("--secret", help="instructor secret; prefer LAB_SECRET environment variable")
    parser.add_argument("--demo", action="store_true", help="use the insecure demo secret")
    args = parser.parse_args(list(argv) if argv is not None else None)

    secret = secret_from_args(args)
    student_ids = read_student_ids(args)
    manifest = {
        "format": "repair-fs-public-manifest-v1",
        "students": {
            student_id: public_entry(student_id, secret)
            for student_id in student_ids
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
