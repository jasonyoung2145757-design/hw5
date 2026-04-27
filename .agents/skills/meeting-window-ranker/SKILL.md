---
name: meeting-window-ranker
description: Ranks cross-timezone meeting options from a JSON spec with participant time zones, work-hour windows, and meeting duration. Use when the user needs exact DST-safe time conversion and a deterministic comparison of candidate meeting slots.
---

# Meeting Window Ranker

Use this skill when a user needs a precise ranking of meeting slots across time zones. The deterministic part lives in the Python script: it converts every slot into each participant's local time, handles DST through `zoneinfo`, checks work-hour and preferred-hour windows, and sorts the results with a repeatable heuristic.

## When To Use

- The user provides a meeting duration plus either a search window or explicit candidate slots.
- The user needs an exact comparison across multiple IANA time zones such as `America/New_York` or `Asia/Kolkata`.
- The user wants the best overlap, not a free-form scheduling discussion.
- The user needs a report that shows who is inside work hours, outside work hours, or only outside preferred hours.

## When Not To Use

- Do not use this skill to read live calendars, send invites, or book meetings.
- Do not guess ambiguous time zone abbreviations such as `EST`, `CST`, or `IST`; ask for IANA names instead.
- Do not use this for broad project planning questions that do not include concrete time constraints.
- Do not use this when the user wants subjective negotiation advice rather than deterministic slot ranking.

## Expected Inputs

Prepare a JSON file with:

- `meeting_duration_minutes`
- `participants`
- Either `candidate_window` or `candidate_slots_utc`
- Optional `top_n`

Each participant must include:

- `name`
- `timezone`
- `work_hours`
- Optional `preferred_hours`

See [references/input-format.md](references/input-format.md) for the exact schema and examples.

## Workflow

1. Translate the user's request into the JSON format from `references/input-format.md`.
2. Validate that every timestamp is timezone-aware and every time zone is an IANA identifier.
3. Run with a Python 3.9+ interpreter:

```bash
/usr/bin/python3 scripts/rank_meeting_windows.py --input <path-to-json>
```

4. Read the ranked report and summarize the best slot plus the tradeoffs.
5. If the script rejects the input because the search space is too large or the time zones are ambiguous, do not guess. Ask the user to narrow the window or provide valid IANA zones.

## Output Format

Return:

- A one-paragraph recommendation
- The top-ranked slots from the script output
- A brief note about any hard conflicts, soft conflicts, or overnight meetings

If no slot is perfect, say so clearly and recommend the least-bad option instead of pretending there is a clean overlap.

## Important Checks

- Prefer `candidate_window` when the user wants the script to search possible slots.
- Prefer `candidate_slots_utc` when the user already has fixed candidate times to compare.
- Keep the search bounded. The script rejects oversized windows instead of silently processing thousands of slots.
- Preserve the distinction between:
  - hard conflict: part of the meeting falls outside a participant's work hours
  - soft conflict: inside work hours but outside that participant's preferred hours
  - overnight: the meeting crosses midnight for that participant locally
