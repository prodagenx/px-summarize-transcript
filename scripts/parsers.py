"""Parse meeting transcripts into speaker turns: WebVTT, Teams copy/paste, bracket Markdown, and `Name: text` lines."""
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Turn:
    speaker: str
    start: float | None
    end: float | None
    text: str


class UnsupportedFormat(ValueError):
    pass


FORMATS = ("vtt", "teams-paste", "md-bracket", "speaker-lines")
# Teams copy/paste carries UI icon glyphs (private-use code points) and zero-width marks.
NOISE = re.compile("[\ue000-\uf8ff\u200b-\u200d\u2060\ufeff]")


def clean(body: str) -> str:
    return NOISE.sub("", body)


def to_seconds(stamp: str) -> float:
    parts = [float(p) for p in stamp.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def fmt(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def merge(cues: list[Turn], gap: float) -> list[Turn]:
    turns: list[Turn] = []
    for cue in cues:
        last = turns[-1] if turns else None
        close = gap == float("inf") or (
            last is not None and cue.start is not None and last.end is not None and cue.start - last.end <= gap
        )
        if last and last.speaker == cue.speaker and close:
            last.text = f"{last.text} {cue.text}"
            if cue.end is not None:
                last.end = max(last.end or cue.end, cue.end)
        else:
            turns.append(Turn(cue.speaker, cue.start, cue.end, cue.text))
    return turns


def strip_leading_h1(body: str) -> str:
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        return "\n".join(lines[i + 1:]) if line.startswith("# ") else body
    return body


# --- WebVTT -----------------------------------------------------------------

TIMING = re.compile(r"^\s*([\d:.]+)\s*-->\s*([\d:.]+)")
VOICE = re.compile(r"<v\s+([^>]+)>")
TAG = re.compile(r"</?[^>]*>")


def parse_vtt(raw: str) -> list[Turn]:
    cues = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
        lines = block.strip().split("\n")
        timing_index = next((i for i, line in enumerate(lines) if TIMING.match(line)), None)
        if timing_index is None:
            continue
        match = TIMING.match(lines[timing_index])
        body = "\n".join(lines[timing_index + 1:])
        voice = VOICE.search(body)
        speaker = voice.group(1).strip() if voice else "Unknown"
        text = " ".join(TAG.sub("", body).split())
        if text:
            cues.append(Turn(speaker, to_seconds(match.group(1)), to_seconds(match.group(2)), text))
    return merge(sorted(cues, key=lambda cue: cue.start), gap=2.0)


# --- Teams copy/paste -------------------------------------------------------

DURATION = r"(?:(?P<h>\d+) hours? ?)?(?:(?P<m>\d+) minutes? ?)?(?:(?P<s>\d+) seconds?)?"
CLOCK = re.compile(rf"^{DURATION}\d{{1,2}}(?::\d{{2}}){{1,2}}$")
ANCHOR = re.compile(rf"^(?P<speaker>.+?) {DURATION}$")
EVENT = re.compile(r"^(?P<name>.+?) (?P<action>started|stopped) transcription$", re.IGNORECASE)
INITIALS = re.compile(r"^[A-Z]{1,3}$")


def _duration_seconds(match: re.Match) -> float | None:
    h, m, s = match.group("h"), match.group("m"), match.group("s")
    if h is None and m is None and s is None:
        return None
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)


def is_clock(line: str) -> bool:
    match = CLOCK.match(line)
    return bool(match) and _duration_seconds(match) is not None


def parse_teams(raw: str) -> tuple[list[Turn], list[str]]:
    lines = [line.replace("\xa0", " ").strip() for line in raw.replace("\r\n", "\n").split("\n")]
    n = len(lines)
    # A speaker name sits on the line directly above each "N minutes N seconds0:03" clock line.
    speakers = {lines[i] for i in range(n - 1) if lines[i] and is_clock(lines[i + 1])}

    def next_nonblank(i: int) -> int:
        while i < n and not lines[i]:
            i += 1
        return i

    cues: list[Turn] = []
    events: list[str] = []
    current: Turn | None = None
    for i, line in enumerate(lines):
        if not line or is_clock(line):
            continue
        if event := EVENT.match(line):
            events.append(f"{event.group('action').lower()} by {event.group('name')}")
            continue
        if i + 1 < n and is_clock(lines[i + 1]):
            continue
        if INITIALS.match(line):
            j = next_nonblank(i + 1)
            if j + 1 < n and is_clock(lines[j + 1]):
                continue
        anchor = ANCHOR.match(line)
        if anchor and anchor.group("speaker") in speakers and (start := _duration_seconds(anchor)) is not None:
            current = Turn(anchor.group("speaker"), start, start, "")
            cues.append(current)
            continue
        if current:
            current.text = f"{current.text} {line}".strip()
    return merge([cue for cue in cues if cue.text], gap=float("inf")), events


# --- Bracket Markdown: "[Speaker] YYYY-MM-DD HH:MM:SS" then text lines -------

BRACKET = re.compile(r"^\[(?P<speaker>.+?)\]\s+(?P<date>\d{4}-\d{2}-\d{2})[ T](?P<time>\d{1,2}:\d{2}:\d{2})\s*$")


def parse_md_bracket(raw: str) -> tuple[list[Turn], dict]:
    cues: list[Turn] = []
    first: datetime | None = None
    current: Turn | None = None
    for line in raw.replace("\r\n", "\n").split("\n"):
        header = BRACKET.match(line.strip())
        if header:
            stamp = datetime.fromisoformat(f"{header.group('date')} {header.group('time').zfill(8)}")
            first = first or stamp
            offset = (stamp - first).total_seconds()
            current = Turn(header.group("speaker").strip(), offset, offset, "")
            cues.append(current)
        elif current and line.strip():
            current.text = f"{current.text} {line.strip()}".strip()
    meta = {}
    if first:
        meta = {"meeting_date": first.date().isoformat(), "meeting_start": first.strftime("%H:%M:%S")}
    return merge([cue for cue in cues if cue.text], gap=float("inf")), meta


# --- Speaker-labeled lines without times: "Name: text" -----------------------

SPEAKER_LINE = re.compile(r"^(?P<speaker>[A-Z][\w.'\-]*(?: [\w.'\-]+){0,4}):\s+(?P<text>\S.*)$")


def parse_speaker_lines(raw: str) -> list[Turn]:
    cues: list[Turn] = []
    current: Turn | None = None
    for line in raw.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        labeled = SPEAKER_LINE.match(stripped)
        if labeled:
            current = Turn(labeled.group("speaker"), None, None, labeled.group("text").strip())
            cues.append(current)
        elif current and stripped:
            current.text = f"{current.text} {stripped}"
    return merge(cues, gap=float("inf"))


# --- Detection --------------------------------------------------------------

def detect_format(body: str) -> str:
    lines = [line.replace("\xa0", " ").strip() for line in body.replace("\r\n", "\n").split("\n")]
    if body.lstrip().startswith("WEBVTT"):
        return "vtt"
    if any(BRACKET.match(line) for line in lines):
        return "md-bracket"
    if any(is_clock(line) for line in lines):
        return "teams-paste"
    if sum(1 for line in lines if SPEAKER_LINE.match(line)) >= 2:
        return "speaker-lines"
    raise UnsupportedFormat(
        "Unrecognized transcript format. Supported: WebVTT, Teams copy/paste, "
        "'[Speaker] YYYY-MM-DD HH:MM:SS' blocks, or 'Speaker: text' lines."
    )


def parse(body: str) -> tuple[str, list[Turn], list[str], dict]:
    """Return (format, turns, transcription events, meta) for a transcript body without frontmatter."""
    body = clean(body)
    kind = detect_format(body)
    if kind == "vtt":
        return kind, parse_vtt(body), [], {}
    if kind == "teams-paste":
        turns, events = parse_teams(body)
        return kind, turns, events, {}
    if kind == "md-bracket":
        turns, meta = parse_md_bracket(body)
        return kind, turns, [], meta
    return kind, parse_speaker_lines(strip_leading_h1(body)), [], {}
