"""Check every [T### (HH:MM:SS) Speaker] "quote" citation in a summary report against its turn index."""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

import frontmatter
from bundle import SUMMARY, sha256

TURN = re.compile(r"^\[T(?P<id>\d+)\](?: (?P<time>\d{2}:\d{2}:\d{2}))? (?P<speaker>[^:]+?): (?P<text>.*)$")
CITATION = re.compile(r'\[T(?P<id>\d+)(?: (?P<time>\d{2}:\d{2}:\d{2}))? (?P<speaker>[^"\n]+?)\]\s*"(?P<quote>[^"]*)"')
ELLIPSIS = re.compile(r"\.\.\.|…")
MAX_WORDS = 25


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}))
    return " ".join(text.lower().split())


def load_turns(path: Path) -> dict[str, dict]:
    turns = {}
    for line in frontmatter.body_of(path).splitlines():
        match = TURN.match(line)
        if match:
            turns[str(int(match.group("id")))] = match.groupdict()
    return turns


def check(summary: Path, turns_path: Path, strict: bool) -> int:
    turns = load_turns(turns_path)
    body = frontmatter.body_of(summary)
    failures, warnings, total = [], [], 0
    for lineno, line in enumerate(body.splitlines(), 1):
        for cite in CITATION.finditer(line):
            total += 1
            label = f"line {lineno} [T{cite.group('id')}]"
            turn = turns.get(str(int(cite.group("id"))))
            if not turn:
                failures.append(f"{label}: turn not found")
                continue
            if cite.group("speaker").strip() != turn["speaker"].strip():
                failures.append(f"{label}: speaker {cite.group('speaker')!r} != {turn['speaker']!r}")
            if cite.group("time") and turn["time"] and cite.group("time") != turn["time"]:
                failures.append(f"{label}: time {cite.group('time')} != {turn['time']}")
            text = normalize(turn["text"])
            for fragment in ELLIPSIS.split(cite.group("quote")):
                piece = normalize(fragment).strip(" ,.;:!?")
                if piece and piece not in text:
                    failures.append(f"{label}: quote not in turn: {fragment.strip()!r}")
            words = len(ELLIPSIS.sub(" ", cite.group("quote")).split())
            if words > MAX_WORDS:
                (failures if strict else warnings).append(f"{label}: quote has {words} words (max {MAX_WORDS})")

    recorded = frontmatter.get(summary, "turns-sha256")
    if recorded and recorded != sha256(frontmatter.body_of(turns_path)):
        warnings.append("turn index changed since this report was stamped (turns-sha256 mismatch)")

    print(f"{summary.name}: {total} citations, {len(failures)} failures, {len(warnings)} warnings")
    for item in failures:
        print(f"  FAIL {item}")
    for item in warnings:
        print(f"  WARN {item}")
    return 1 if failures or total == 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", help="Path to <stem>.summary.md (or a .vN version)")
    parser.add_argument("--turns", help="Turn index (default: <stem>.turns.md beside the report)")
    parser.add_argument("--strict", action="store_true", help="Treat quotes over 25 words as failures")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    summary = Path(args.summary).resolve()
    match = SUMMARY.match(summary.name)
    turns = Path(args.turns).resolve() if args.turns else (
        summary.parent / f"{match.group('stem')}.turns.md" if match else None)
    if not summary.exists() or not turns or not turns.exists():
        print(f"error: summary or turn index not found ({summary.name}, {turns})", file=sys.stderr)
        return 2
    return check(summary, turns, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
