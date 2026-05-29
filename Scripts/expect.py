#!/usr/bin/env python3

# Copyright (c) 2025 Institute of Parallel And Distributed Systems (IPADS), Shanghai Jiao Tong University (SJTU)
# Licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.

"""
Expect script for grading lab assignments.
Better to use this script with Python 3.7 and later.
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import re
import select
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import TypedDict

if sys.version_info[0] != 3 or sys.version_info[1] < 6:
    print(
        "This script requires Python version 3.7 and later. Please upgrade your Python version to grade this lab."
    )
    sys.exit(255)

try:
    import pexpect
except ImportError:
    pexpect = None


def _color(code: str) -> str:
    return code if sys.stdout.isatty() else ""


class Colors:
    """ANSI color codes"""

    BLACK = _color("\033[0;30m")
    RED = _color("\033[0;31m")
    GREEN = _color("\033[0;32m")
    BROWN = _color("\033[0;33m")
    BLUE = _color("\033[0;34m")
    PURPLE = _color("\033[0;35m")
    CYAN = _color("\033[0;36m")
    LIGHT_GRAY = _color("\033[0;37m")
    DARK_GRAY = _color("\033[1;30m")
    LIGHT_RED = _color("\033[1;31m")
    LIGHT_GREEN = _color("\033[1;32m")
    YELLOW = _color("\033[1;33m")
    LIGHT_BLUE = _color("\033[1;34m")
    LIGHT_PURPLE = _color("\033[1;35m")
    LIGHT_CYAN = _color("\033[1;36m")
    LIGHT_WHITE = _color("\033[1;37m")
    BOLD = _color("\033[1m")
    FAINT = _color("\033[2m")
    ITALIC = _color("\033[3m")
    UNDERLINE = _color("\033[4m")
    BLINK = _color("\033[5m")
    NEGATIVE = _color("\033[7m")
    CROSSED = _color("\033[9m")
    END = _color("\033[0m")


@dataclass
class LineExpect:
    """Line capture definition. Used for parsing scores.json in lab folders."""

    content: str
    msg: str
    proposed: int
    actual: int = 0
    userland: bool = False


class RawExpect(TypedDict):
    capture: str
    msg: str
    proposed: int
    actual: int
    userland: bool


def load_captures(file: str, in_kernel: bool) -> list[LineExpect]:

    captures: list[LineExpect] = list()
    try:
        with open(file, "rb") as f:
            raw_captures: list[RawExpect] = json.load(f)

    except FileNotFoundError:
        print(f"File: {file} not found.")
        raise
    except json.JSONDecodeError:
        print(f"File: {file} is not a valid JSON file.")
        raise

    for index, raw_capture in enumerate(raw_captures):
        try:
            captures.append(
                LineExpect(
                    content=raw_capture["capture"],
                    msg=raw_capture["msg"],
                    proposed=raw_capture["proposed"],
                    userland=raw_capture.get("userland", False) if in_kernel else True,
                )
            )
        except KeyError:
            print(f"Invalid line {index} capture definition.")
            raise
    return captures


def expect_with_subprocess(
    command: list[str], patterns: list[str], timeout: int, verbose: bool
) -> list[int]:
    matched_indices: list[int] = []
    compiled_patterns = [re.compile(pattern) for pattern in patterns]
    process = subprocess.Popen(
        " ".join(command),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if process.stdout is None:
        return matched_indices

    fd = process.stdout.fileno()
    buffer = ""
    deadline = time.time() + timeout

    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        ready, _, _ = select.select([fd], [], [], min(0.1, remaining))
        if ready:
            chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
            if not chunk:
                break
            if verbose:
                print(chunk, end="")
            buffer += chunk

            while True:
                matched = False
                for i, pattern in enumerate(compiled_patterns):
                    match = pattern.search(buffer)
                    if match is None:
                        continue
                    matched_indices.append(i)
                    buffer = buffer[match.end() :]
                    matched = True
                    break
                if not matched:
                    # Keep the tail to match patterns spanning chunk boundaries.
                    buffer = buffer[-4096:]
                    break
        elif process.poll() is not None:
            break

    process.terminate()
    process.wait(timeout=1)
    return matched_indices


def main(args: argparse.Namespace):
    """Main grading function."""

    is_kernel_test = args.serial != ""

    captures = load_captures(args.file, is_kernel_test)

    expect_lines = [
        (
            f"{capture.content}: {args.serial}"
            if not capture.userland
            else f"{capture.content}"
        )
        for capture in captures
    ]

    if is_kernel_test:
        expect_lines += [f"End of Kernel Checkpoints: {args.serial}.*"]

    logging.debug(f"Expecting: {expect_lines}")
    proposed_total = sum([capture.proposed for capture in captures])
    in_userland = not is_kernel_test
    scores = 0

    if len(expect_lines) > 0:
        if pexpect is not None:
            process = pexpect.spawn(
                " ".join(args.command), timeout=args.timeout, encoding="utf-8"
            )
            process.logfile = sys.stdout if args.verbose else None
            while scores < proposed_total:
                try:
                    i = process.expect(expect_lines)

                    logging.debug(f"Matched: {expect_lines[i]}")
                    if i == len(expect_lines) - 1 and is_kernel_test:
                        logging.debug("End of Kernel Checkpoints detected.")
                        in_userland = True
                    else:
                        if in_userland == captures[i].userland and captures[i].actual == 0:
                            captures[i].actual = captures[i].proposed
                            scores += captures[i].actual
                        else:
                            logging.debug(
                                f"Userland Mismatch or duplicate: {in_userland} != {captures[i].userland}"
                            )
                except (pexpect.EOF, pexpect.TIMEOUT, KeyboardInterrupt):
                    break
            process.close()
        else:
            logging.debug("pexpect unavailable, falling back to subprocess mode.")
            matched_indices = expect_with_subprocess(
                args.command, expect_lines, args.timeout, args.verbose
            )
            for i in matched_indices:
                logging.debug(f"Matched: {expect_lines[i]}")
                if i == len(expect_lines) - 1 and is_kernel_test:
                    logging.debug("End of Kernel Checkpoints detected.")
                    in_userland = True
                else:
                    if in_userland == captures[i].userland and captures[i].actual == 0:
                        captures[i].actual = captures[i].proposed
                        scores += captures[i].actual
                    else:
                        logging.debug(
                            f"Userland Mismatch or duplicate: {in_userland} != {captures[i].userland}"
                        )

    for capture in captures:
        print(f"{capture.msg}: {capture.actual}/{capture.proposed}")

    return scores


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="A simple grader script on listening to the stdout."
    )

    _ = parser.add_argument(
        "-f",
        "--file",
        type=str,
        dest="file",
        required=True,
        help="Score definition on certain lines of stdout.",
    )

    _ = parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        dest="timeout",
        required=True,
        help="Timeout for the grading process.",
    )

    _ = parser.add_argument(
        "-s",
        "--serial",
        type=str,
        dest="serial",
        required=False,
        default="",
        help="Serial Number to proceed.",
    )

    _ = parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        required=False,
        default=False,
        help="Verbose mode.",
    )
    _ = parser.add_argument(
        "command", nargs=argparse.REMAINDER, help="Real Command to grade."
    )

    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        format=f"{Colors.GREEN}[EXPECT]: %(message)s{Colors.END}",
        level=log_level,
    )
    scores = main(args)
    sys.exit(scores)
