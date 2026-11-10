"""List transcripts in a folder and how far each one has been processed. Prints JSON.

Status: new (no turn index), turns-only (no report yet), summarized, or not-a-transcript.
"""
import argparse
import json
import sys
from pathlib import Path

from bundle import GENERATED, SOURCE_EXTS, Bundle, BundleError, analyze


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", help="Folder to scan")
    parser.add_argument("--recursive", action="store_true", help="Include subfolders")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"error: not a folder: {folder}", file=sys.stderr)
        return 2
    files = folder.rglob("*") if args.recursive else folder.iterdir()
    rows = []
    for path in sorted(files):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTS or GENERATED.search(path.name):
            continue
        bundle = Bundle(path)
        try:
            analyze(bundle)
        except (BundleError, ValueError):
            rows.append({"path": str(path), "status": "not-a-transcript"})
            continue
        latest = bundle.latest_summary()
        status = "summarized" if latest else "turns-only" if bundle.turns.exists() else "new"
        rows.append({"path": str(path), "status": status, "latest_summary": str(latest) if latest else None})

    pending = [r for r in rows if r["status"] in ("new", "turns-only")]
    print(json.dumps({"folder": str(folder), "pending": len(pending), "transcripts": rows}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
