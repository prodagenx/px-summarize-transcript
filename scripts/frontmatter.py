"""Minimal, line-based YAML frontmatter editing. Foreign keys are kept verbatim, never re-serialized."""
import json
import re
from pathlib import Path

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY = re.compile(r"^([A-Za-z0-9_][\w-]*)\s*:(.*)$")


def split(text: str) -> tuple[list[str] | None, str, str]:
    """Return (frontmatter lines or None, body, newline)."""
    # Files written on Windows often mix LF and CRLF, so match lines on any ending and keep the body's bytes as-is.
    raw = text.splitlines(keepends=True)
    nl = "\r\n" if raw and raw[0].endswith("\r\n") else "\n"
    if not raw or raw[0].strip() != "---":
        return None, text, nl
    for i in range(1, len(raw)):
        if raw[i].strip() == "---":
            return [line.rstrip("\r\n") for line in raw[1:i]], "".join(raw[i + 1:]), nl
    return None, text, nl


def read(path: Path) -> tuple[list[str] | None, str, str]:
    if not path.exists():
        return None, "", "\n"
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return split(handle.read())


def body_of(path: Path) -> str:
    return read(path)[1]


def blocks(fm: list[str] | None) -> dict[str, list[str]]:
    """Group frontmatter lines into top-level key blocks, preserving order."""
    out: dict[str, list[str]] = {}
    current = None
    for line in fm or []:
        match = KEY.match(line)
        if match and not line[:1].isspace():
            current = match.group(1)
            out[current] = [line]
        elif current:
            out[current].append(line)
        else:
            out.setdefault("", []).append(line)
    return out


def _unquote(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value.strip('"')
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def scalar(block: list[str] | None) -> str | None:
    if not block:
        return None
    value = KEY.match(block[0]).group(2).strip()
    return _unquote(value) if value else None


def items(block: list[str] | None) -> list[str]:
    if not block:
        return []
    inline = KEY.match(block[0]).group(2).strip()
    if inline.startswith("["):
        return [_unquote(v) for v in inline.strip("[]").split(",") if v.strip()]
    return [_unquote(line.strip()[2:]) for line in block[1:] if line.strip().startswith("- ")]


def get(path: Path, key: str) -> str | None:
    return scalar(blocks(read(path)[0]).get(key))


def _quote(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    return text if DATE.match(text) else json.dumps(text, ensure_ascii=False)


def render(key: str, value) -> list[str]:
    if isinstance(value, dict):
        return [f"{key}:"] + [f"  {k}: {_quote(v)}" for k, v in value.items()]
    if isinstance(value, (list, tuple)):
        return [f"{key}: []"] if not value else [f"{key}:"] + [f"  - {_quote(v)}" for v in value]
    return [f"{key}: {_quote(value)}"]


def apply(path: Path, values: dict, *, keep_existing: set[str] | None = None, refresh: set[str] | None = None,
          body: str | None = None) -> None:
    """Merge `values` into the file's frontmatter. None values are skipped.

    keep_existing: keys never overwritten when already present (generated files).
    refresh: if given, only these keys are overwritten when present; all other existing keys are kept (source files).
    body: replace the body when given; otherwise the existing body is kept byte-for-byte.
    """
    fm, old_body, nl = read(path)
    current = blocks(fm)
    for key, value in values.items():
        if value is None:
            continue
        if key in current:
            if keep_existing and key in keep_existing:
                continue
            if refresh is not None and key not in refresh:
                continue
        current[key] = render(key, value)
    lines = [line for block in current.values() for line in block]
    new_body = old_body if body is None else body.replace("\n", nl) if nl != "\n" else body
    if fm is None and not new_body.startswith(nl):
        new_body = nl + new_body
    text = nl.join(["---", *lines, "---"]) + nl + new_body
    path.write_text(text, encoding="utf-8", newline="")
