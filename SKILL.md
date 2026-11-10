---
name: px-summarize-transcript
description: 'Extract decisions, material statements, action items, and open questions from a meeting transcript (.vtt, Teams copy/paste .txt, or Markdown .md), with speaker attribution and timestamped verbatim evidence, and save them as a linked bundle with frontmatter next to the transcript. Assigns owners to action items, tracks what carried over from the previous meeting in a series, and can file transcripts into series folders. Use for /px-summarize-transcript, Teams/Zoom/Webex transcripts, meeting minutes, "what was decided", "who said", "action items from the call", "pull decisions from transcript", "meeting recap with evidence", "summarize this transcript", "what is still open from last meeting", "process the pending transcripts in this folder".'
argument-hint: 'Path to the transcript (.vtt, .txt, or .md), or a folder of transcripts. Optionally: "for <your name>".'
license: MIT
metadata:
  author: prodagenx
  version: "2.3.0"
---

# px-summarize-transcript

Turns a meeting transcript into an evidence-backed record of what was decided, what material facts were stated, and who owns what next. Every item cites the speaker, timestamp (when the transcript has one), and a verbatim quote. Python scripts do the mechanical work: parsing, file naming, frontmatter, and quote checks. You do the reasoning.

## When to Use

- A `.vtt`, a Teams transcript pasted into `.txt` or `.md`, a `[Speaker] YYYY-MM-DD HH:MM:SS` Markdown transcript, or `Name: text` lines need decisions and action items pulled out.
- Someone asks who said something, what was agreed, or who owns a follow-up.
- Someone asks what is still open from the previous meeting in a recurring series.
- Meeting outcomes must be reconciled against project documents.

## Bundle layout (fixed)

All files sit in the transcript's own folder and share its file name. Only the suffix changes. You cannot write them anywhere else. If the user asks for another folder, explain that the bundle stays with its transcript. `file_transcript.py` can move a whole bundle into a series folder, and its members always move together.

| File | Role |
|---|---|
| `<stem>.vtt` / `.txt` / `.md` | Source transcript. `.md` and `.txt` get frontmatter merged in place; existing keys are never changed. |
| `<stem>.source.md` | `.vtt` only: a small Markdown "sidecar" that holds the `.vtt`'s frontmatter, because a `.vtt` file must start with `WEBVTT` and can't hold frontmatter itself. |
| `<stem>.turns.md` | Turn index. Created once; never rewritten unless you pass `--rebuild`. |
| `<stem>.summary.md` | Report. Re-runs write `<stem>.summary.v2.md`, `.v3`, and so on. |

Formats and keys: [input formats](./references/input-formats.md), [frontmatter spec](./references/frontmatter-spec.md).

## Procedure

The scripts sit in `./scripts/` beside this SKILL.md. The terminal starts in the user's workspace, so resolve the skill folder's absolute path first (personal installs are usually `~/.claude/skills/px-summarize-transcript` or `~/.agents/skills/px-summarize-transcript`) and set it once per terminal:

```powershell
$S = "<absolute path to this skill>\scripts"      # PowerShell
```

```bash
S="<absolute path to this skill>/scripts"          # bash / zsh
```

Commands below use PowerShell (`"$S\build_turns.py"`). In bash, write `"$S/build_turns.py"`. The scripts use only the standard library (Python 3.10+). Quote paths, because file names often contain spaces.

Work on one transcript at a time. For a folder or "everything pending", see [Several transcripts](#several-transcripts).

1. **File the transcript (optional).** Do this when the user asks, or when the workspace keeps transcripts in series folders (for example `transcripts/<series>/`) and this one isn't in one yet. `--root` defaults to `./transcripts`.

   ```powershell
   python "$S\file_transcript.py" --list --root "<root>"
   python "$S\file_transcript.py" "<transcript>" --series "<series>" --root "<root>"
   ```

   Reuse an existing series that fits the meeting. If none fits, propose a short kebab-case name and confirm it with the user before creating it. Then act on `status`:
   - `moved`: continue with the new `source` path.
   - `already-filed`: the transcript is already inside a folder under the root, or in a folder named after the series. Nothing moved, so continue.
   - `duplicate`: the same transcript already exists at `duplicate_of`. Stop and ask the user which copy to process. Don't delete either file.
   - `conflict` (exit code 2): a different file with the same name is already in the series folder. Stop and ask.

2. **Build the turn index.**

   ```powershell
   python "$S\build_turns.py" "<transcript>"
   ```

   It detects the format, writes `<stem>.turns.md` if it doesn't exist yet, stamps the source (or sidecar), and prints JSON. Keep `turns_path`, `turns_status`, `summary_path`, `has_timestamps`, `speakers`, `meeting_date`, `meeting_date_source`, `gaps`, `previous_meeting_summary`, and `transcription`.
   - `turns_status: created` or `kept`: continue. `kept` means the existing turn index already matches the transcript, so nothing was rewritten.
   - `turns_status: source-changed` (exit code 3): the transcript was edited after the turn index was built, and existing reports cite the old turn IDs. Stop and ask the user before re-running with `--rebuild`.
   - Unsupported-format error (exit code 2): tell the user which formats are supported and stop.
   - `meeting_date` is `null`: write "Not stated" unless the user gives you the date.

3. **Read the full turn index** in large chunks until the end. Never extract from a partial read.

4. **Map the speakers.** Make one row per speaker label for the report's Speakers table: the label, the name to show, and how you identified it.
   - Show a different name only with evidence: the person is addressed by name, introduces themselves, or the label is an obvious misspelling. Record the evidence.
   - A conference-room device label stays the room. List who was heard or addressed there, and don't attribute its lines to one person unless the transcript makes it unambiguous.
   - People named only in the `Transcription:` header line attended but did not necessarily speak.
   - List people who are mentioned but don't speak, with where they were mentioned.
   - Resolve first names to full names only when unambiguous.

5. **Extract items** using these tests:
   - **Decision:** a choice between options was made or accepted ("let's go with", "agreed", "we'll do", or a proposal with no objection). Status: Agreed, Tentative, or Proposed.
   - **Material statement:** something that would change scope, design, schedule, cost, or risk if it were wrong: facts about systems, constraints, dependencies, numbers, dates, commitments, stated risks. Not small talk or restatements. Aim for 12 or fewer by merging related statements.
   - **Action item:** a future task with a verb, asked for or volunteered ("I'll", "can you", "we need to").
   - **Open question:** raised and not resolved before the meeting moved on.

6. **Assign owners** to each action item. Owners can be anyone named, including people who are absent.
   - **Explicit:** named and asked, did not decline.
   - **Volunteered:** the speaker said "I'll ...".
   - **Delegated:** assigned to someone absent or silent. Mark `(not present)` and note who assigned it.
   - **Inferred:** follows from stated role or ownership. Write the reasoning.
   - **Unassigned:** none of the above. Never invent an owner.

   Record due dates only if they were said.

7. **Attach evidence** to every item:
   - With timestamps: `[T042 00:12:31 Speaker] "verbatim quote"`.
   - Without timestamps (`has_timestamps: false`): `[T042 Speaker] "verbatim quote"`.
   - `Speaker` is the label exactly as in the turn index, even when the Speakers table shows a different name. Use display names everywhere else.
   - Quotes are 25 words or fewer, copied exactly including ASR errors. Use `...` for omissions. Cite several turns when a decision forms across turns.

8. **Check what carried over** (only when `previous_meeting_summary` is set). Read only the Action items and Open questions tables of that report. For each item, decide from this transcript whether it is Done, In progress, Still open, Dropped, or Not mentioned, and cite the turn that shows it. Never mark an item Done without someone saying so.

9. **Write the report** to `summary_path` using [the template](./references/report-template.md). Write the body only; do not add frontmatter. Always fill in "At a glance". Add "For \<Name\>" only when the user names the reader, for example "for me, I'm Dana Ruiz". Never assume who the reader is.

10. **Flag transcription caveats:** likely ASR errors, speaker names you mapped by inference, and every entry in `gaps` (content may be missing). Never silently correct quotes.

11. **Verify quotes** and fix or drop every failing row until it passes:

    ```powershell
    python "$S\verify_quotes.py" "<summary_path>"
    ```

12. **Finalize the bundle.** Derive a short title from the meeting content and 3 to 6 topic tags (lowercase, kebab-case). `transcript` and `meeting-notes` are added automatically.

    ```powershell
    python "$S\finalize_bundle.py" "<transcript>" --summary "<summary_path>" --title "<title>" --tags "tag-one,tag-two" --alias "Label in transcript=Display name" --mentioned "Name (context)" --meeting-date YYYY-MM-DD
    ```

    - `--alias` repeats once per speaker label you mapped in step 4. Attendees then default to the display names.
    - `--mentioned` repeats once per person.
    - `--attendee "Name"` repeats once per person when you need to override the attendee list. `--attendees "A, B (room: C, D)"` also works, because commas inside `()` or `[]` don't split.
    - Pass `--meeting-date` only when `meeting_date` was `null` and the user gave you the date.

13. **Report back in chat** briefly. Don't paste the tables.
    - Counts: decisions, statements, action items, open questions, and carried-over items.
    - The "At a glance" bullets.
    - Anything that needs a human check: inferred speaker names, inferred or unassigned owners, gaps, and ASR caveats.
    - Links to the report and the turn index.

## Several transcripts

```powershell
python "$S\scan.py" "<folder>" --recursive
```

It lists every transcript as `new`, `turns-only`, `summarized`, or `not-a-transcript`. Show the user the pending ones (`new` and `turns-only`) and confirm before starting. Process them one at a time, oldest meeting first, so each one can find the previous meeting in its series. Run the full procedure and report back for each before starting the next.

## Related project documents

If the workspace has related architecture or planning docs (including other bundles' summary files), fill in the optional "Related project documents" table. Note whether each item confirms, contradicts, or extends what those docs record.

## Quality checks

- `verify_quotes.py` passes with 0 failures.
- The Speakers table has a row for every label in the turn index, and every name mapping states its evidence.
- No owner is named without explicit, volunteered, delegated, or explained inferred evidence.
- Decisions marked Agreed show an acceptance signal, not just a suggestion.
- Opinions and speculation are labeled as such.
- Owners who were not in the meeting are marked `(not present)`.
- Every entry in `gaps` appears under Transcription caveats.
- When there's a previous meeting, every one of its action items and open questions has a Carried over row.

## Legacy bundles

To align older bundles (for example `input.txt` next to `<folder>.turns.md`), run `python "$S\backfill.py" "<root>"` for a dry run, then `--apply`. Then run `finalize_bundle.py` per bundle with a title and tags. Backfill never regenerates an existing turn index, so existing citations stay valid.
