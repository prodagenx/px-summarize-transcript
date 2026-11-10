"""File a transcript, and any bundle files beside it, into <root>/<series>/. Prints JSON.

Never nests: a transcript already inside a folder under <root>, or already in a folder named after the series,
is left where it is. Use --list to see existing series folders before choosing a name.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import frontmatter
from bundle import GENERATED, SOURCE_EXTS, Bundle, BundleError, kebab, sha256

MEMBER_SUFFIX = re.compile(r"\.(turns|source|summary(\.v\d+)?)\.md")


def is_source(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SOURCE_EXTS and not GENERATED.search(path.name)


def series_folders(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def members(bundle: Bundle) -> list[Path]:
    stem = bundle.stem
    extra = [p for p in bundle.folder.iterdir()
             if p.is_file() and p.name.startswith(stem) and MEMBER_SUFFIX.fullmatch(p.name[len(stem):])]
    return [bundle.source, *sorted(extra)]


def body_hash(path: Path) -> str:
    return sha256(frontmatter.body_of(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", nargs="?", help="Transcript to file (.vtt, .txt, .md)")
    parser.add_argument("--series", help="Series folder name, e.g. 'weekly-standup'. An existing folder with the same kebab-case name is reused.")
    parser.add_argument("--root", default="transcripts", help="Folder that holds the series folders (default: ./transcripts)")
    parser.add_argument("--list", action="store_true", help="List existing series folders and exit")
    parser.add_argument("--dry-run", action="store_true", help="Report what would move without moving anything")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(args.root).expanduser().resolve()

    if args.list:
        print(json.dumps({"root": str(root), "series": [
            {"name": p.name, "transcripts": sum(is_source(f) for f in p.iterdir())} for p in series_folders(root)
        ]}, indent=2, ensure_ascii=False))
        return 0
    if not args.transcript or not args.series:
        parser.error("transcript and --series are required unless --list is used")

    try:
        bundle = Bundle.from_input(args.transcript)
    except BundleError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    wanted = kebab(args.series)
    if not wanted:
        print(f"error: --series {args.series!r} has no usable characters", file=sys.stderr)
        return 2
    existing = next((p for p in series_folders(root) if kebab(p.name) == wanted), None)
    target = existing or root / wanted
    folder = bundle.folder
    result = {"source": str(bundle.source), "target_folder": str(target), "moved": []}

    if (root in folder.parents) or kebab(folder.name) == wanted:
        result["status"] = "already-filed"
        result["target_folder"] = str(folder)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if target.is_dir():
        digest = body_hash(bundle.source)
        twin = next((f for f in target.iterdir() if is_source(f) and body_hash(f) == digest), None)
        if twin:
            result.update(status="duplicate", duplicate_of=str(twin))
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        clashes = [p.name for p in members(bundle) if (target / p.name).exists()]
        if clashes:
            result.update(status="conflict", clashes=clashes)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("error: files with these names already exist in the series folder", file=sys.stderr)
            return 2

    result["status"] = "would-move" if args.dry_run else "moved"
    if not args.dry_run:
        target.mkdir(parents=True, exist_ok=True)
    for path in members(bundle):
        if not args.dry_run:
            path.rename(target / path.name)
        result["moved"].append(str(target / path.name))
    result["source"] = result["moved"][0]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
