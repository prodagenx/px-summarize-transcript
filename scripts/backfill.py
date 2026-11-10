"""Align legacy transcript bundles to the shared-stem layout. Dry run by default; --apply renames and rewrites links."""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import quote

import frontmatter
from bundle import SUMMARY

HEADER = re.compile(r"^# Transcript turns: (?P<name>.+?)\s*$", re.M)


def plan(root: Path) -> list[dict]:
    bundles = []
    for turns in sorted(root.rglob("*.turns.md")):
        stem = turns.name[: -len(".turns.md")]
        folder = turns.parent
        header = HEADER.search(frontmatter.body_of(turns))
        candidates = [folder / header.group("name")] if header else []
        candidates += [folder / f"{stem}{ext}" for ext in (".vtt", ".txt", ".md")]
        source = next((c for c in candidates if c.is_file()), None)
        summaries = sorted(p for p in folder.glob("*.md")
                           if (m := SUMMARY.match(p.name)) and m.group("stem") == stem)
        item = {"stem": stem, "folder": folder, "turns": turns, "source": source, "summaries": summaries,
                "rename": None, "problem": None}
        if not source:
            item["problem"] = "source transcript not found"
        else:
            target = folder / f"{stem}{source.suffix}"
            if source.name != target.name:
                item["problem"] = f"{target.name} already exists" if target.exists() else None
                item["rename"] = None if item["problem"] else target
        bundles.append(item)
    return bundles


def rewrite_links(path: Path, old: str, new: str) -> bool:
    fm, body, nl = frontmatter.read(path)
    updated = body
    for a, b in ((old, new), (quote(old), quote(new))):
        updated = updated.replace(a, b)
    if updated == body:
        return False
    head = nl.join(["---", *fm, "---"]) + nl if fm is not None else ""
    path.write_text(head + updated, encoding="utf-8", newline="")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Folder to scan for *.turns.md bundles")
    parser.add_argument("--apply", action="store_true", help="Perform renames and link rewrites")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    skill_dir = Path(__file__).resolve().parent
    for item in plan(Path(args.root).resolve()):
        print(f"\n[{item['stem']}] {item['folder']}")
        if item["problem"]:
            print(f"  SKIP: {item['problem']}")
            continue
        source = item["source"]
        if item["rename"]:
            target = item["rename"]
            print(f"  rename {source.name} -> {target.name}")
            for doc in [item["turns"], *item["summaries"]]:
                print(f"  relink {doc.name}: {source.name} -> {target.name}")
            if args.apply:
                source.rename(target)
                for doc in [item["turns"], *item["summaries"]]:
                    rewrite_links(doc, source.name, target.name)
                source = target
        else:
            print("  names already aligned")
        print(f'  next: python "{skill_dir / "finalize_bundle.py"}" "{source}" --title "..." --tags "..."')
    if not args.apply:
        print("\nDry run only. Re-run with --apply to make these changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
