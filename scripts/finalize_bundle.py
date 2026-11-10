"""Stamp shared frontmatter (title, tags, people, links, counts) on every member of a transcript bundle."""
import argparse
import json
import sys
from pathlib import Path

from bundle import FIXED_TAGS, Bundle, BundleError, analyze, kebab, stamp_source, stamp_summary, stamp_turns


def split_list(value: str) -> list[str]:
    """Split on commas that are not inside () or [], so "Room (Ana, Bo)" stays one entry."""
    parts, depth, current = [], 0, ""
    for char in value:
        if char in "([":
            depth += 1
        elif char in ")]" and depth:
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    return [p.strip() for p in parts + [current] if p.strip()]


def parse_aliases(values: list[str]) -> dict[str, str]:
    aliases = {}
    for value in values:
        raw, sep, shown = value.partition("=")
        if not sep or not raw.strip() or not shown.strip():
            raise BundleError(f'Bad --alias {value!r}. Use "Label in transcript=Display name".')
        aliases[raw.strip()] = shown.strip()
    return aliases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", help="Path to the original transcript (.vtt, .txt, .md)")
    parser.add_argument("--summary", "--decisions", dest="summary",
                        help="Summary file to stamp (default: latest version in the bundle)")
    parser.add_argument("--title", required=True, help="Meeting title derived from context")
    parser.add_argument("--tags", default="", help="Comma-separated topic tags; transcript and meeting-notes are always added")
    parser.add_argument("--attendees", help="Comma-separated attendees; commas inside () or [] are kept")
    parser.add_argument("--attendee", action="append", default=[], help="Repeatable: one attendee per flag")
    parser.add_argument("--alias", action="append", default=[],
                        help='Repeatable: "Label in transcript=Display name" for mislabeled or room-device speakers')
    parser.add_argument("--mentioned", action="append", default=[], help='Repeatable: "Name (context)"')
    parser.add_argument("--meeting-date", help="YYYY-MM-DD when the transcript does not carry it")
    parser.add_argument("--extraction-date", help="YYYY-MM-DD (default: existing value or today)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        bundle = Bundle.from_input(args.transcript)
        if not bundle.turns.exists():
            raise BundleError(f"Missing {bundle.turns.name}. Run build_turns.py first.")
        summary = Path(args.summary).resolve() if args.summary else bundle.latest_summary()
        if not summary or not summary.exists():
            raise BundleError("No summary file found. Write the report first.")
        if summary.parent != bundle.folder:
            raise BundleError("The summary file must be in the same folder as the transcript.")
        bundle.version_of(summary)
        info = analyze(bundle)
        aliases = parse_aliases(args.alias)
        unknown = [raw for raw in aliases if raw not in info["speakers"]]
        if unknown:
            raise BundleError(f"--alias labels not found among speakers: {', '.join(unknown)}")
    except (BundleError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    tags = list(dict.fromkeys(FIXED_TAGS + [kebab(t) for t in args.tags.split(",") if kebab(t)]))
    attendees = (split_list(args.attendees) if args.attendees else []) + [a.strip() for a in args.attendee if a.strip()]
    attendees = attendees or list(dict.fromkeys(aliases.get(s, s) for s in info["speakers"]))
    shared = {
        "title": args.title.strip(),
        "tags": tags,
        "attendees": attendees,
        "aliases": [f"{raw} = {shown}" for raw, shown in aliases.items()] or None,
        "mentioned": [m.strip() for m in args.mentioned if m.strip()] or None,
        "meeting_date": args.meeting_date,
        "summary": summary,
    }
    stamp_source(bundle, info, **shared)
    stamp_turns(bundle, info, **shared)
    shared.pop("summary")
    stamp_summary(bundle, info, summary, extraction_date=args.extraction_date, **shared)

    stamped = [bundle.source if not bundle.sidecar else bundle.sidecar, bundle.turns, summary]
    print(json.dumps({"bundle": bundle.stem, "stamped": [str(p) for p in stamped], "tags": tags}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
