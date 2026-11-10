# Input formats

`build_turns.py` strips any YAML frontmatter, then detects the format in this order. The first match wins.

| Order | Format (`source-format`) | Detected by | Timestamps in turn index |
|---|---|---|---|
| 1 | `vtt` | Body starts with `WEBVTT` | Cue offsets. Same-speaker cues within 2 s merge. |
| 2 | `md-bracket` | Any line `[Speaker] YYYY-MM-DD HH:MM:SS` | Offset from the first line (`00:00:00`). Date and start time go to frontmatter. |
| 3 | `teams-paste` | Any Teams clock line such as `0 minutes 3 seconds0:03` | Offsets from the pasted clock. |
| 4 | `speaker-lines` | At least two `Name: text` lines | None. Turns are `[T001] Name: text`. |

Anything else fails with an error listing these formats. Consecutive turns by the same speaker merge into one turn (except `vtt`, which uses the 2 s gap).

## Samples

**vtt**

```text
WEBVTT

30cf7e78-.../14-0
00:01:44.314 --> 00:01:45.594
<v Alex Kim>Hello, hello.</v>
```

**md-bracket** (frontmatter optional)

```text
[Priya Shah] 2026-10-09 13:18:44
Morning.
[Jordan Lee] 2026-10-09 13:18:45
Hey.
```

**teams-paste** (in `.txt` or `.md`)

```text
Jordan Lee started transcription
SD
Sam Diaz
0 minutes 7 seconds0:07
Sam Diaz 0 minutes 7 seconds
It.
```

Avatar initials (`SD`) are dropped. `started/stopped transcription` lines go to the `Transcription:` header.

**speaker-lines**

```text
Jordan Lee: Let's go with the database option.
It keeps the audit trail.
Alex Kim: Agreed. I'll check with the platform team.
```

Unlabeled lines continue the previous speaker's turn. Labels are 1 to 5 words starting with a capital letter.

## Turn index layout

```text
# Transcript turns: <source file name>
Speakers (N): Name, Name
Turns: N
Transcription: started by Name; stopped by Name   (teams-paste only)

[T001] 00:00:03 Name: text      (with timestamps)
[T001] Name: text               (speaker-lines)
```

## Meeting date

`build_turns.py` reports `meeting_date` and where it came from in `meeting_date_source`, checking in this order:

1. `transcript`: the transcript itself (`md-bracket` only).
2. `frontmatter`: the source keys `meeting-date` or `date`.
3. `filename`: a `YYYY-MM-DD` date, or a `YYMMDD` token such as `261009-Solutioning`, in the file name.

If all three are empty, `meeting_date` is `null`. Pass `--meeting-date` to `finalize_bundle.py` when the user tells you the date.

## Gaps

`build_turns.py` lists silences of 3 minutes or more between consecutive turns in `gaps` (change with `--gap-minutes`). In a Teams copy/paste, a gap usually means only the entries visible on screen were copied. Each gap goes under "Transcription caveats" in the report. Transcripts without timestamps never report gaps.
