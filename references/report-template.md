# Report template

Use this structure for the file at `summary_path` from `build_turns.py` (`<stem>.summary.md`, or `<stem>.summary.vN.md` on re-runs). Write the body only: `finalize_bundle.py` adds the frontmatter. Keep IDs stable (D1, M1, A1, Q1, C1) so later edits can reference them. Every row in the Decisions, Material statements, Action items, and Open questions tables needs at least one evidence citation in the form `[T042 00:12:31 Speaker]`, or `[T042 Speaker]` when the transcript has no timestamps.

**Names:** citations always use the speaker label exactly as it appears in the turn index, so `verify_quotes.py` can check them. Everywhere else (Decided by, Said by, Owner, At a glance) use the display name from the Speakers table.

Leave out optional sections entirely when they don't apply. Don't write "None" placeholders.

```markdown
# <Meeting title>: decisions, statements, and action items

- **Source:** [<stem>.<ext>](<stem>.<ext>) (encode spaces as `%20` in the link target)
- **Turn index:** [<stem>.turns.md](<stem>.turns.md)
- **Meeting date:** YYYY-MM-DD (from transcript / frontmatter / file name / user), or "Not stated"
- **Previous meeting:** [<previous summary file>](<previous summary file>) (only when build_turns.py found one)
- **Attendees (spoke):** Display name, Display name, ...
- **Mentioned, not present:** Name (context), ...
- **Extraction date:** YYYY-MM-DD

## Summary

Three to five sentences: purpose of the meeting, the most important decisions, and the biggest open risk.

## At a glance

- **Key decisions:** D1 (four to eight words), D3 (...), D4 (...)
- **Action items by owner:**
  - Display name: A1, A3
  - Display name (not present): A5
  - Unassigned: A9
- **Biggest risks:** M3 (four to eight words), M15 (...)
- **Needs a human check:** 2 speaker labels mapped by inference, 1 gap in the transcript (see Transcription caveats)

### For <Name> (optional)

Only when the user names the reader ("for me, I'm Dana Ruiz", "summarize this for Dana"). List that person's action items, items waiting on them, and decisions or risks that touch their areas, by ID.

## Speakers

| Label in transcript | Shown as | How identified |
|---|---|---|
| Jordan Lee | Jordan Lee | Transcript label |
| Jrdan | Jordan Lee | Misspelled label. Addressed as "Jordan" in [T028] |
| ROOM-4B [Teams] | ROOM-4B room (Sam, Ana, others) | Conference room device. Sam and Ana are addressed by name in [T021], [T066] |

Include every label that appears in the turn index. Room devices stay one row: list the people heard or addressed there. Don't attribute a room-device line to one named person unless the transcript makes it unambiguous.

## Decisions

| ID | Decision | Status | Decided by | Evidence |
|---|---|---|---|---|
| D1 | What was agreed, stated as an outcome | Agreed / Tentative / Proposed | Who proposed and who agreed | [T042 00:12:31 Name] "short verbatim quote" |

## Material statements

Aim for 12 or fewer. Merge statements about the same topic and drop anything that wouldn't change scope, design, schedule, cost, or risk.

| ID | Statement | Type | Said by | Evidence |
|---|---|---|---|---|
| M1 | Paraphrase of the fact, constraint, risk, or commitment | Fact / Constraint / Risk / Dependency / Commitment / Metric | Name | [T010 00:03:05 Name] "short verbatim quote" |

## Action items

| ID | Action | Owner | Assignment | Due | Evidence |
|---|---|---|---|---|---|
| A1 | Verb-first task | Name, Name (not present), or Unassigned | Explicit / Volunteered / Delegated / Inferred / Unassigned | Date or "not stated" | [T055 00:20:10 Name] "short verbatim quote" |

## Open questions

| ID | Question | Raised by | Suggested owner | Evidence |
|---|---|---|---|---|
| Q1 | Unresolved question | Name | Name or "none" | [T060 00:22:41 Name] "short verbatim quote" |

## Carried over from the previous meeting (optional)

Only when `build_turns.py` returned `previous_meeting_summary`. One row per action item and open question in that report.

| ID | Previous item | Status | Evidence |
|---|---|---|---|
| C1 | A3: Set up a regular sync (Jordan Lee) | Done / In progress / Still open / Dropped / Not mentioned | [T012 00:02:40 Jordan Lee] "short verbatim quote", or "not mentioned" |

## Transcription caveats

- `[T005]` "a cure" may be a mistranscription of the product name "Acquire". Not corrected in quotes.
- Gap of 7.5 minutes between `[T120]` (00:41:10) and `[T121]` (00:48:40). Content may be missing from the transcript.

## Related project documents (optional)

| Item | Affects | Note |
|---|---|---|
| D1 | `path/to/doc.md` | Confirms / contradicts / extends a recorded decision |
```

## Field rules

- **Status:** `Agreed` needs an explicit acceptance signal from a decision maker or no objection after a clear proposal. `Tentative` means agreement pending a check. `Proposed` means raised without agreement.
- **Assignment:**
  - `Explicit`: someone was named and asked, for example "Sam, can you send the spec?"
  - `Volunteered`: the speaker took the task, for example "I'll set up the call."
  - `Delegated`: a speaker gave the task to someone absent or silent, for example "Ana needs to confirm the schema." Add `(not present)` after the owner's name.
  - `Inferred`: the owner follows from role or context. State the reasoning in the Action cell.
  - `Unassigned`: no owner can be identified. Never guess a name.
- **Carried over status:** `Done` needs someone saying it happened. `Dropped` needs someone saying it won't happen. If the item isn't discussed, use `Not mentioned`; never assume it is done.
- **Quotes:** verbatim from the turn index, 25 words or fewer, with `...` for omissions. Do not fix grammar or ASR errors inside quotes.
