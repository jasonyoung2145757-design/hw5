# Week 5: Reusable AI Skill

## Skill

This project builds `meeting-window-ranker`, a narrow reusable skill for ranking cross-timezone meeting slots. I chose this idea because it has a clear deterministic core that a model should not improvise: exact time-zone conversion, DST-safe local-time calculation, overnight work-window handling, and repeatable ranking of candidate meeting times.

The skill lives in `.agents/skills/meeting-window-ranker/` and combines:

- `SKILL.md` for activation logic, workflow, and limits
- `scripts/rank_meeting_windows.py` for deterministic scheduling analysis
- `references/input-format.md` for the JSON schema the agent should assemble before running the script

## Why This Fits The Assignment

This is not a one-off prompt. The same skill can be reused whenever a team needs to compare meeting options across cities. The Python script is genuinely load-bearing because prose alone is unreliable for:

- converting UTC slots into each participant's local time
- handling daylight saving time with standard-library `zoneinfo`
- checking overnight work-hour windows such as `22:00` to `06:00`
- sorting the candidate slots with a deterministic heuristic

Without the script, the agent would be guessing about exact offsets, edge cases, and ranking consistency.

## How To Use It

1. Prepare a JSON input file that matches `.agents/skills/meeting-window-ranker/references/input-format.md`.
2. Run with a Python 3.9+ interpreter:

```bash
/usr/bin/python3 .agents/skills/meeting-window-ranker/scripts/rank_meeting_windows.py --input demo/normal-case.json
```

3. Let the agent summarize the top result in plain English.

The script accepts two modes:

- `candidate_window`: search a UTC range at fixed intervals
- `candidate_slots_utc`: compare explicit candidate start times

## What The Script Does

`rank_meeting_windows.py` parses a JSON spec, validates time zones and timestamps, generates or loads candidate slots, converts every slot into each participant's local time, checks work-hour and preferred-hour windows, and outputs a ranked Markdown report.

It requires Python 3.9+ because it relies on the standard-library `zoneinfo` module.

The report distinguishes between:

- hard conflicts: part of the meeting falls outside work hours
- soft conflicts: inside work hours but outside preferred hours
- overnight meetings: the meeting crosses midnight locally

## Test Prompts Used

The assignment asks for at least three prompts. I prepared them in `demo/prompts.md` and backed them with sample JSON files:

- `demo/normal-case.json`: standard cross-timezone ranking
- `demo/edge-case-overnight.json`: overnight work-window edge case
- `demo/cautious-case-ambiguous-timezone.json`: partial decline because `EST` and `CST` are ambiguous

## What Worked Well

- A narrow task kept the skill reusable and easy to trigger.
- The deterministic script cleanly handled math-heavy scheduling logic.
- Using JSON inputs made the workflow easy for an agent to orchestrate.
- The cautious case demonstrates that the skill should refuse to guess ambiguous time zones.

## Remaining Limitations

- The skill does not integrate with live calendars or send meeting invites.
- The ranking heuristic is rule-based, not personalized beyond the declared work/preferred windows.
- The input must already contain a concrete duration and either candidate slots or a search window.

## Video Link

[Watch the demo video](https://youtu.be/HByfc56_QJI)

## Suggested Video Flow

For the walkthrough, show:

1. the folder structure under `.agents/skills/meeting-window-ranker/`
2. the `name` and `description` in `SKILL.md`
3. the core logic in `scripts/rank_meeting_windows.py`
4. one successful run on `demo/normal-case.json`
5. one edge-case run on `demo/edge-case-overnight.json`
6. one cautious run on `demo/cautious-case-ambiguous-timezone.json`
