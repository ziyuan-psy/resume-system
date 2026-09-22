from __future__ import annotations

import json
import re


def decode_scalar(value: str) -> str:
    value = value.strip()
    if not value or value == "[]":
        return ""
    try:
        return str(json.loads(value))
    except json.JSONDecodeError:
        return value.strip('"')


def find_value(lines: list[str], key: str, start: int = 0, end: int | None = None) -> str:
    end = len(lines) if end is None else end
    pattern = re.compile(rf"^\s*(?:-\s+)?{re.escape(key)}:\s*(.*)$")
    for index in range(start, end):
        match = pattern.match(lines[index])
        if not match:
            continue
        inline = match.group(1).strip()
        if inline:
            return decode_scalar(inline)
        for next_index in range(index + 1, end):
            candidate = lines[next_index].strip()
            if not candidate:
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", candidate):
                return ""
            return decode_scalar(candidate)
    return ""


def find_block(lines: list[str], key: str) -> tuple[int, int]:
    start = -1
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:\s*$", line):
            start = index + 1
            break
    if start == -1:
        return -1, -1
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index] and not lines[index].startswith(" "):
            end = index
            break
    return start, end


def parse_list_block(lines: list[str], key: str) -> list[str]:
    start, end = find_block(lines, key)
    if start == -1:
        return []
    values: list[str] = []
    for line in lines[start:end]:
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(decode_scalar(stripped[2:]))
    return values


def parse_entry_segments(lines: list[str], item_key: str) -> list[tuple[int, int]]:
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(rf"^\s*-\s+{re.escape(item_key)}:", line)
    ]
    return [(start, starts[pos + 1] if pos + 1 < len(starts) else len(lines)) for pos, start in enumerate(starts)]


def parse_nested_list(segment: list[str], key: str) -> list[str]:
    start = -1
    base_indent = 0
    for index, line in enumerate(segment):
        match = re.match(rf"^(\s*){re.escape(key)}:\s*(.*)$", line)
        if match:
            start = index + 1
            base_indent = len(match.group(1))
            if match.group(2).strip() == "[]":
                return []
            break
    if start == -1:
        return []
    values = []
    for line in segment[start:]:
        if line.strip().startswith("- "):
            values.append(decode_scalar(line.strip()[2:]))
            continue
        if line.strip() and len(line) - len(line.lstrip(" ")) <= base_indent:
            break
    return values
