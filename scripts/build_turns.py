"""Build <stem>.turns.md next to a transcript (.vtt, .txt, .md) and stamp bundle frontmatter. Prints a JSON summary.

The turn index is deterministic, so an existing one is never rewritten unless --rebuild is passed.
"""
import argparse
import json
import sys

import frontmatter
from bundle import FIXED_TAGS, Bundle, BundleError, analyze, find_gaps, render_turns, stamp_source, write_turns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", help="Path to the transcript. Output always goes to the same folder.")
    parser.add_argument("--rebuild", action="store_true",
                        help="Regenerate an existing turn index (only after the source transcript changed)")
    parser.add_argument("--gap-minutes", type=float, default=3.0,
                        help="Report silences of at least this many minutes between turns (default: 3)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        bundle = Bundle.from_input(args.transcript)
        info = analyze(bundle)
    except (BundleError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    latest = bundle.latest_summary()
    if not bundle.turns.exists():
        status = "created"
    elif args.rebuild:
        status = "rebuilt"
    else:
        current = frontmatter.body_of(bundle.turns).replace("\r\n", "\n").strip("\n")
        status = "kept" if current == render_turns(bundle, info).strip("\n") else "source-changed"

    if status in ("created", "rebuilt"):
        turns_fm = frontmatter.blocks(frontmatter.read(bundle.turns)[0])
        shared = {
            "title": frontmatter.scalar(turns_fm.get("title")) or bundle.stem,
            "tags": frontmatter.items(turns_fm.get("tags")) or FIXED_TAGS,
            "attendees": frontmatter.items(turns_fm.get("attendees")) or info["speakers"],
            "summary": latest,
        }
        write_turns(bundle, info, **shared)
        if bundle.sidecar:
            stamp_source(bundle, info, **shared)
        else:
            stamp_source(bundle, info, **{**shared, "title": None, "tags": None})

    print(json.dumps({
        "bundle": bundle.stem,
        "folder": str(bundle.folder),
        "source": str(bundle.source),
        "format": info["format"],
        "has_timestamps": info["has_timestamps"],
        "speakers": info["speakers"],
        "turn_count": len(info["turns"]),
        "transcription": info["events"],
        "meeting_date": info["meeting_date"],
        "meeting_date_source": info["meeting_date_source"],
        "meeting_start": info["meeting_start"],
        "duration": info["duration"],
        "gaps": find_gaps(info["turns"], args.gap_minutes),
        "source_sha256": info["source_sha256"],
        "turns_path": str(bundle.turns),
        "turns_status": status,
        "sidecar_path": str(bundle.sidecar) if bundle.sidecar else None,
        "latest_summary": str(latest) if latest else None,
        "summary_path": str(bundle.next_summary()),
        "previous_meeting_summary": str(prev) if (prev := bundle.previous_meeting(info["meeting_date"])) else None,
    }, indent=2, ensure_ascii=False))
    if status == "source-changed":
        print("error: the transcript no longer matches its turn index. Existing reports cite the old turn IDs. "
              "Re-run with --rebuild only if you want a new turn index, then write a new summary version.",
              file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
