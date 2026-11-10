# Frontmatter spec

Every bundle member carries frontmatter so the files read as one bundle in Obsidian and other tools. Keys are kebab-case. Links are Obsidian wikilinks (`"[[name]]"`, `.md` extension dropped). Dates are `YYYY-MM-DD`.

## Shared keys

| Key | Value | Notes |
|---|---|---|
| `filename` | This file's name | |
| `title` | Meeting title derived from content | Set by `finalize_bundle.py --title` |
| `doc-role` | `source`, `source-meta`, `turns`, `summary` | `source-meta` is the `.vtt` sidecar (`<stem>.source.md`) |
| `bundle` | Shared stem | Same for every member |
| `cdate` | Created date | Kept once set. First stamp uses the file's creation date. |
| `mdate` | Last modified by the skill | Updated every run |
| `created-by` | `px-summarize-transcript` | |
| `skill-version` | e.g. `2.3.0` | |
| `status` | `draft` | Kept once set, so you can change it to `reviewed` |
| `tags` | `transcript`, `meeting-notes`, plus 3-6 derived topic tags | |
| `meeting-date` | Meeting date | From the transcript, source frontmatter, file name, or `--meeting-date`. Omitted when unknown |
| `meeting-start` | `HH:MM:SS` | `md-bracket` sources only |
| `duration` | `HH:MM:SS` | Omitted for `speaker-lines` |
| `attendees` | Display names of speakers, or `--attendee` / `--attendees` | |
| `speaker-aliases` | `Label in transcript = Display name` entries | From `--alias`. Omitted when no label was mapped |
| `mentioned-not-present` | `Name (context)` entries | From `--mentioned` |
| `source-format` | `vtt`, `md-bracket`, `teams-paste`, `speaker-lines` | |
| `has-timestamps` | `true` / `false` | |
| `bundle-source` | `"[[<stem>.vtt]]"` or `"[[<stem>]]"` | |
| `bundle-source-meta` | `"[[<stem>.source]]"` | `.vtt` bundles only |
| `bundle-turns` | `"[[<stem>.turns]]"` | |
| `bundle-summary` | Latest summary version | |

## Role-specific keys

| Role | Keys |
|---|---|
| `turns` | `turn-count`, `speaker-count`, `source-sha256` (hash of the transcript body) |
| `source-meta` | `source-sha256` |
| `summary` | `extraction-date`, `counts` (`decisions`, `statements`, `actions`, `questions`, `carried-over`), `turns-sha256`, `supersedes` (previous version, v2+), `follows` (summary of the previous meeting in the same folder, by `meeting-date`) |

## Merge rules

- **Source `.md` / `.txt`:** keys are added only when missing. Existing keys (for example `date`, `source`, `duration`, `participants`) are never changed. The skill refreshes only its own bookkeeping keys: `mdate`, `doc-role`, `bundle`, `skill-version`, `source-format`, `has-timestamps`, and the `bundle-*` links. The transcript body is kept byte-for-byte.
- **Generated files:** the skill owns every key except `cdate` and `status`, which are kept once set. Unknown keys you add by hand are kept.
- `verify_quotes.py` warns when a report's `turns-sha256` no longer matches its turn index.
