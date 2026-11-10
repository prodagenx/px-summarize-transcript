"""Bundle model shared by the px-summarize-transcript scripts: paths, analysis, turn index, and frontmatter stamping."""
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import frontmatter
from parsers import Turn, fmt, parse

SKILL = "px-summarize-transcript"
VERSION = "2.3.0"
FIXED_TAGS = ["transcript", "meeting-notes"]
SOURCE_EXTS = {".vtt", ".txt", ".md"}
SUMMARY = re.compile(r"^(?P<stem>.*)\.summary(?:\.v(?P<n>\d+))?\.md$")
GENERATED = re.compile(r"\.(turns|source|summary(\.v\d+)?)\.md$")
# Keys the skill may refresh on a source file; every other existing source key is left untouched.
SOURCE_REFRESH = {"mdate", "doc-role", "bundle", "skill-version", "source-format", "has-timestamps",
                  "bundle-source", "bundle-source-meta", "bundle-turns", "bundle-summary"}
KEEP_ON_GENERATED = {"cdate", "status"}
ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
# YYMMDD as a whole token, e.g. "261009-Solutioning".
SHORT_DATE = re.compile(r"(?<![^\s_.-])(\d{2})(\d{2})(\d{2})(?![^\s_.-])")


class BundleError(ValueError):
    pass


def today() -> str:
    return date.today().isoformat()


def file_cdate(path: Path) -> str:
    if not path.exists():
        return today()
    st = path.stat()
    return datetime.fromtimestamp(getattr(st, "st_birthtime", st.st_ctime)).date().isoformat()


def sha256(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").strip("\n").encode("utf-8")).hexdigest()


def wikilink(path: Path) -> str:
    name = path.name[:-3] if path.suffix == ".md" else path.name
    return f"[[{name}]]"


def kebab(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def date_from_name(name: str) -> str | None:
    for pattern, century in ((ISO_DATE, ""), (SHORT_DATE, "20")):
        for match in pattern.finditer(name):
            year, month, day = match.groups()
            try:
                return date(int(century + year), int(month), int(day)).isoformat()
            except ValueError:
                continue
    return None


def find_gaps(turns: list[Turn], minutes: float) -> list[dict]:
    """Silences between consecutive turns of at least `minutes`, a sign of missing transcript content."""
    gaps = []
    for i in range(1, len(turns)):
        prev, cur = turns[i - 1], turns[i]
        if prev.start is None or cur.start is None:
            continue
        last = prev.end if prev.end is not None else prev.start
        if cur.start - last >= minutes * 60:
            gaps.append({"after": f"T{i:03d}", "before": f"T{i + 1:03d}", "from": fmt(last),
                         "to": fmt(cur.start), "minutes": round((cur.start - last) / 60, 1)})
    return gaps


@dataclass
class Bundle:
    source: Path

    @classmethod
    def from_input(cls, value: str | Path) -> "Bundle":
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise BundleError(f"Input not found: {path}")
        if path.suffix.lower() not in SOURCE_EXTS:
            raise BundleError(f"Unsupported input type {path.suffix!r}. Use .vtt, .txt, or .md.")
        if GENERATED.search(path.name):
            raise BundleError(f"{path.name} is a generated bundle file. Pass the original transcript instead.")
        return cls(path)

    @property
    def stem(self) -> str:
        return self.source.name[: -len(self.source.suffix)]

    @property
    def folder(self) -> Path:
        return self.source.parent

    @property
    def is_vtt(self) -> bool:
        return self.source.suffix.lower() == ".vtt"

    @property
    def turns(self) -> Path:
        return self.folder / f"{self.stem}.turns.md"

    @property
    def sidecar(self) -> Path | None:
        return self.folder / f"{self.stem}.source.md" if self.is_vtt else None

    def summary_versions(self) -> list[tuple[int, Path]]:
        found = []
        for path in self.folder.glob("*.md"):
            match = SUMMARY.match(path.name)
            if match and match.group("stem") == self.stem:
                found.append((int(match.group("n") or 1), path))
        return sorted(found)

    def latest_summary(self) -> Path | None:
        versions = self.summary_versions()
        return versions[-1][1] if versions else None

    def next_summary(self) -> Path:
        versions = self.summary_versions()
        if not versions:
            return self.folder / f"{self.stem}.summary.md"
        return self.folder / f"{self.stem}.summary.v{versions[-1][0] + 1}.md"

    def version_of(self, summary: Path) -> int:
        match = SUMMARY.match(summary.name)
        if not match or match.group("stem") != self.stem:
            raise BundleError(f"{summary.name} is not a summary file for bundle {self.stem!r}.")
        return int(match.group("n") or 1)

    def previous_meeting(self, meeting_date: str | None) -> Path | None:
        """Latest summary of another bundle in this folder whose meeting-date is before this meeting."""
        if not meeting_date:
            return None
        latest: dict[str, tuple[int, Path]] = {}
        for path in self.folder.glob("*.md"):
            match = SUMMARY.match(path.name)
            if match and match.group("stem") != self.stem:
                n = int(match.group("n") or 1)
                if n > latest.get(match.group("stem"), (0, None))[0]:
                    latest[match.group("stem")] = (n, path)
        dated = [(frontmatter.get(p, "meeting-date"), p) for _, p in latest.values()]
        earlier = [(d, p) for d, p in dated if d and d < meeting_date]
        return max(earlier)[1] if earlier else None


def analyze(bundle: Bundle) -> dict:
    fm, body, _ = frontmatter.read(bundle.source)
    source_keys = frontmatter.blocks(fm)
    if bundle.sidecar and bundle.sidecar.exists():
        source_keys = {**frontmatter.blocks(frontmatter.read(bundle.sidecar)[0]), **source_keys}
    kind, turns, events, meta = parse(body)
    if not turns:
        raise BundleError(f"No speaker turns found in {bundle.source.name} (detected format: {kind}).")
    has_times = turns[0].start is not None
    ends = [t.end for t in turns if t.end is not None]
    duration = None
    if has_times and kind in ("vtt", "teams-paste", "md-bracket"):
        duration = fmt(max(ends) if kind == "vtt" else turns[-1].start)
    candidates = (
        ("transcript", meta.get("meeting_date")),
        ("frontmatter", frontmatter.scalar(source_keys.get("meeting-date"))
         or frontmatter.scalar(source_keys.get("date"))),
        ("filename", date_from_name(bundle.stem)),
    )
    date_source, meeting_date = next(((k, v) for k, v in candidates if v), (None, None))
    return {
        "format": kind,
        "turns": turns,
        "events": events,
        "has_timestamps": has_times,
        "speakers": sorted({t.speaker for t in turns}),
        "meeting_date": meeting_date,
        "meeting_date_source": date_source,
        "meeting_start": meta.get("meeting_start"),
        "duration": duration,
        "source_sha256": sha256(body),
    }


def render_turns(bundle: Bundle, info: dict) -> str:
    turns: list[Turn] = info["turns"]
    lines = [
        f"# Transcript turns: {bundle.source.name}",
        f"Speakers ({len(info['speakers'])}): {', '.join(info['speakers'])}",
        f"Turns: {len(turns)}",
    ]
    if info["events"]:
        lines.append(f"Transcription: {'; '.join(info['events'])}")
    lines.append("")
    for i, t in enumerate(turns, 1):
        when = f" {fmt(t.start)}" if t.start is not None else ""
        lines.append(f"[T{i:03d}]{when} {t.speaker}: {t.text}")
    return "\n".join(lines) + "\n"


def links(bundle: Bundle, summary: Path | None) -> dict:
    return {
        "bundle-source": wikilink(bundle.source),
        "bundle-source-meta": wikilink(bundle.sidecar) if bundle.sidecar else None,
        "bundle-turns": wikilink(bundle.turns),
        "bundle-summary": wikilink(summary) if summary else None,
    }


def common(bundle: Bundle, info: dict, path: Path, role: str, *, title=None, tags=None, attendees=None,
           mentioned=None, meeting_date=None, summary=None, aliases=None) -> dict:
    values = {
        "filename": path.name,
        "title": title,
        "doc-role": role,
        "bundle": bundle.stem,
        "cdate": file_cdate(path),
        "mdate": today(),
        "created-by": SKILL,
        "skill-version": VERSION,
        "status": "draft",
        "tags": tags,
        "meeting-date": meeting_date or info["meeting_date"],
        "meeting-start": info["meeting_start"],
        "duration": info["duration"],
        "attendees": attendees,
        "speaker-aliases": aliases,
        "mentioned-not-present": mentioned,
        "source-format": info["format"],
        "has-timestamps": info["has_timestamps"],
    }
    values.update(links(bundle, summary))
    return values


def stamp_source(bundle: Bundle, info: dict, **shared) -> None:
    """Merge frontmatter into the source (.md/.txt in place) or the .vtt sidecar."""
    if bundle.sidecar:
        values = common(bundle, info, bundle.sidecar, "source-meta", **shared)
        values["source-sha256"] = info["source_sha256"]
        body = f"\n# {values['title'] or bundle.stem}\n\nMetadata for {wikilink(bundle.source)}. The transcript itself stays unchanged.\n"
        existing_body = frontmatter.body_of(bundle.sidecar) if bundle.sidecar.exists() else None
        frontmatter.apply(bundle.sidecar, values, keep_existing=KEEP_ON_GENERATED,
                          body=None if existing_body else body)
    else:
        values = common(bundle, info, bundle.source, "source", **shared)
        frontmatter.apply(bundle.source, values, refresh=SOURCE_REFRESH)


def write_turns(bundle: Bundle, info: dict, **shared) -> None:
    values = common(bundle, info, bundle.turns, "turns", **shared)
    values.update({
        "turn-count": len(info["turns"]),
        "speaker-count": len(info["speakers"]),
        "source-sha256": info["source_sha256"],
    })
    frontmatter.apply(bundle.turns, values, keep_existing=KEEP_ON_GENERATED, body="\n" + render_turns(bundle, info))


def stamp_turns(bundle: Bundle, info: dict, **shared) -> None:
    """Refresh turns frontmatter without regenerating its body (keeps existing citations valid)."""
    body = frontmatter.body_of(bundle.turns)
    values = common(bundle, info, bundle.turns, "turns", **shared)
    count = len(re.findall(r"^\[T\d+\]", body, re.M))
    speakers = re.search(r"^Speakers \((\d+)\)", body, re.M)
    values.update({
        "turn-count": count,
        "speaker-count": int(speakers.group(1)) if speakers else len(info["speakers"]),
        "source-sha256": info["source_sha256"],
    })
    frontmatter.apply(bundle.turns, values, keep_existing=KEEP_ON_GENERATED)


def count_items(text: str) -> dict:
    found = {letter: set() for letter in "DMAQC"}
    for letter, number in re.findall(r"^\|\s*([DMAQC])(\d+)\s*\|", text, re.M):
        found[letter].add(number)
    return {"decisions": len(found["D"]), "statements": len(found["M"]),
            "actions": len(found["A"]), "questions": len(found["Q"]), "carried-over": len(found["C"])}


def stamp_summary(bundle: Bundle, info: dict, summary: Path, *, extraction_date=None, **shared) -> None:
    body = frontmatter.body_of(summary)
    values = common(bundle, info, summary, "summary", summary=summary, **shared)
    version = bundle.version_of(summary)
    previous = [p for n, p in bundle.summary_versions() if n < version]
    stated = re.search(r"\*\*Extraction date:\*\*\s*(\d{4}-\d{2}-\d{2})", body)
    values.update({
        "extraction-date": (extraction_date or (stated.group(1) if stated else None)
                            or frontmatter.get(summary, "extraction-date") or today()),
        "counts": count_items(body),
        "turns-sha256": sha256(frontmatter.body_of(bundle.turns)),
        "supersedes": wikilink(previous[-1]) if previous else None,
    })
    follows = bundle.previous_meeting(values["meeting-date"])
    if follows:
        values["follows"] = wikilink(follows)
    frontmatter.apply(summary, values, keep_existing=KEEP_ON_GENERATED)
