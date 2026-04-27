# Input Format

Use this reference when you need to build the JSON payload for `scripts/rank_meeting_windows.py`.

## Required Top-Level Fields

- `meeting_duration_minutes`: positive integer
- `participants`: array of participant objects
- `candidate_window` or `candidate_slots_utc`

## Optional Top-Level Fields

- `top_n`: how many ranked slots to show in detail

## Participant Object

Each participant object must look like:

```json
{
  "name": "London Design",
  "timezone": "Europe/London",
  "work_hours": { "start": "09:00", "end": "17:30" },
  "preferred_hours": { "start": "10:00", "end": "16:00" }
}
```

Notes:

- `timezone` must be an IANA zone, not an abbreviation.
- `work_hours` and `preferred_hours` use local clock time in `HH:MM`.
- Overnight windows are allowed. Example: `{ "start": "22:00", "end": "06:00" }`.

## Search-Window Mode

Use `candidate_window` when the script should generate candidate slots:

```json
{
  "meeting_duration_minutes": 60,
  "candidate_window": {
    "start": "2026-05-05T12:00:00Z",
    "end": "2026-05-05T18:00:00Z",
    "step_minutes": 30
  },
  "top_n": 3,
  "participants": [
    {
      "name": "NYC Product",
      "timezone": "America/New_York",
      "work_hours": { "start": "09:00", "end": "17:00" },
      "preferred_hours": { "start": "10:00", "end": "16:00" }
    },
    {
      "name": "London Design",
      "timezone": "Europe/London",
      "work_hours": { "start": "09:00", "end": "17:30" },
      "preferred_hours": { "start": "09:30", "end": "16:30" }
    }
  ]
}
```

## Fixed-Candidate Mode

Use `candidate_slots_utc` when the user already has exact options to compare:

```json
{
  "meeting_duration_minutes": 45,
  "candidate_slots_utc": [
    "2026-05-05T13:00:00Z",
    "2026-05-05T15:30:00Z",
    "2026-05-05T17:00:00Z"
  ],
  "participants": [
    {
      "name": "Berlin Engineering",
      "timezone": "Europe/Berlin",
      "work_hours": { "start": "09:00", "end": "17:00" }
    },
    {
      "name": "Tokyo QA",
      "timezone": "Asia/Tokyo",
      "work_hours": { "start": "10:00", "end": "19:00" }
    }
  ]
}
```

## Validation Rules

- All timestamps must include `Z` or an explicit UTC offset.
- `candidate_window.end` must be later than `candidate_window.start`.
- `step_minutes` must be a positive integer.
- The script rejects large search spaces rather than running an unbounded scan.
- The script rejects ambiguous zones like `EST`, `PST`, `CST`, and `IST`.
