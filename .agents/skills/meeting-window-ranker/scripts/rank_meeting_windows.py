#!/usr/bin/env python3
"""Rank cross-timezone meeting windows from a JSON specification."""

import argparse
import json
import sys

if sys.version_info < (3, 9):
    print(
        "This script requires Python 3.9+ because it depends on zoneinfo.",
        file=sys.stderr,
    )
    raise SystemExit(1)

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_SLOTS = 1000
MAX_PARTICIPANTS = 16
MAX_DURATION_MINUTES = 12 * 60


@dataclass
class Participant:
    name: str
    timezone_name: str
    timezone: ZoneInfo
    work_start: int
    work_end: int
    preferred_start: Optional[int]
    preferred_end: Optional[int]


@dataclass
class ParticipantEvaluation:
    name: str
    timezone: str
    local_label: str
    work_status: str
    preferred_status: str
    off_hours_minutes: int
    preferred_gap_minutes: int
    crosses_midnight: bool
    notes: List[str]


@dataclass
class SlotEvaluation:
    utc_start: str
    utc_end: str
    score: int
    hard_conflicts: int
    soft_conflicts: int
    overnight_count: int
    total_off_hours_minutes: int
    total_preferred_gap_minutes: int
    participants: List[ParticipantEvaluation]


class InputError(ValueError):
    """Raised when the input JSON is invalid or ambiguous."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank cross-timezone meeting slots from a JSON payload."
    )
    parser.add_argument("--input", required=True, help="Path to the input JSON file.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format. Defaults to markdown.",
    )
    return parser.parse_args()


def parse_iso8601(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InputError(f"Invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise InputError(
            f"Timestamp must include a timezone offset or Z suffix: {value}"
        )
    return parsed.astimezone(timezone.utc)


def parse_minutes(value: str, field_name: str) -> int:
    parts = value.split(":")
    if len(parts) != 2:
        raise InputError(f"{field_name} must use HH:MM format: {value}")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise InputError(f"{field_name} must use HH:MM format: {value}") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise InputError(f"{field_name} is out of range: {value}")
    return hour * 60 + minute


def load_timezone(name: str) -> ZoneInfo:
    if "/" not in name:
        raise InputError(
            f"Ambiguous timezone '{name}'. Use an IANA timezone such as "
            "'America/New_York' or 'Europe/London'."
        )
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise InputError(f"Unknown timezone: {name}") from exc


def load_participants(payload: dict[str, Any]) -> List[Participant]:
    raw_participants = payload.get("participants")
    if not isinstance(raw_participants, list) or not raw_participants:
        raise InputError("participants must be a non-empty array")
    if len(raw_participants) > MAX_PARTICIPANTS:
        raise InputError(f"participants may not exceed {MAX_PARTICIPANTS}")

    participants: List[Participant] = []
    for item in raw_participants:
        if not isinstance(item, dict):
            raise InputError("Each participant must be an object")
        name = str(item.get("name", "")).strip()
        if not name:
            raise InputError("Each participant needs a non-empty name")
        timezone_name = str(item.get("timezone", "")).strip()
        timezone_obj = load_timezone(timezone_name)

        work_hours = item.get("work_hours")
        if not isinstance(work_hours, dict):
            raise InputError(f"Participant '{name}' is missing work_hours")
        work_start = parse_minutes(str(work_hours.get("start", "")), f"{name} work start")
        work_end = parse_minutes(str(work_hours.get("end", "")), f"{name} work end")

        preferred_hours = item.get("preferred_hours")
        preferred_start: Optional[int] = None
        preferred_end: Optional[int] = None
        if preferred_hours is not None:
            if not isinstance(preferred_hours, dict):
                raise InputError(f"Participant '{name}' preferred_hours must be an object")
            preferred_start = parse_minutes(
                str(preferred_hours.get("start", "")), f"{name} preferred start"
            )
            preferred_end = parse_minutes(
                str(preferred_hours.get("end", "")), f"{name} preferred end"
            )

        participants.append(
            Participant(
                name=name,
                timezone_name=timezone_name,
                timezone=timezone_obj,
                work_start=work_start,
                work_end=work_end,
                preferred_start=preferred_start,
                preferred_end=preferred_end,
            )
        )
    return participants


def time_from_minutes(total_minutes: int) -> time:
    return time(total_minutes // 60, total_minutes % 60)


def window_interval(
    tz: ZoneInfo, base_day: date, start_minutes: int, end_minutes: int
) -> Tuple[datetime, datetime]:
    start_local = datetime.combine(base_day, time_from_minutes(start_minutes)).replace(
        tzinfo=tz
    )
    end_day = base_day if end_minutes > start_minutes else base_day + timedelta(days=1)
    end_local = datetime.combine(end_day, time_from_minutes(end_minutes)).replace(
        tzinfo=tz
    )
    return start_local, end_local


def overlap_minutes(
    slot_start: datetime,
    slot_end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> int:
    start = max(slot_start, window_start)
    end = min(slot_end, window_end)
    if end <= start:
        return 0
    return int((end - start).total_seconds() // 60)


def evaluate_window(
    slot_start: datetime,
    slot_end: datetime,
    start_minutes: int,
    end_minutes: int,
) -> Tuple[int, bool]:
    relevant_days = {
        slot_start.date() - timedelta(days=1),
        slot_start.date(),
        slot_end.date(),
    }
    total_overlap = 0
    fully_inside = False

    for day in sorted(relevant_days):
        window_start, window_end = window_interval(
            slot_start.tzinfo, day, start_minutes, end_minutes
        )
        total_overlap += overlap_minutes(slot_start, slot_end, window_start, window_end)
        if slot_start >= window_start and slot_end <= window_end:
            fully_inside = True

    duration_minutes = int((slot_end - slot_start).total_seconds() // 60)
    return min(duration_minutes, total_overlap), fully_inside


def format_local_label(local_start: datetime, local_end: datetime) -> str:
    if local_start.date() == local_end.date():
        return (
            f"{local_start:%a %H:%M}-{local_end:%H:%M} "
            f"{local_start.tzname()}"
        )
    return (
        f"{local_start:%a %H:%M}-{local_end:%a %H:%M} "
        f"{local_start.tzname()}"
    )


def participant_eval(
    participant: Participant, slot_start_utc: datetime, duration_minutes: int
) -> ParticipantEvaluation:
    slot_end_utc = slot_start_utc + timedelta(minutes=duration_minutes)
    local_start = slot_start_utc.astimezone(participant.timezone)
    local_end = slot_end_utc.astimezone(participant.timezone)

    work_overlap, inside_work = evaluate_window(
        local_start, local_end, participant.work_start, participant.work_end
    )
    off_hours_minutes = max(0, duration_minutes - work_overlap)
    if inside_work:
        work_status = "inside"
    elif work_overlap > 0:
        work_status = "partial"
    else:
        work_status = "outside"

    preferred_status = "not_set"
    preferred_gap_minutes = 0
    if participant.preferred_start is not None and participant.preferred_end is not None:
        preferred_overlap, inside_preferred = evaluate_window(
            local_start,
            local_end,
            participant.preferred_start,
            participant.preferred_end,
        )
        preferred_gap_minutes = max(0, duration_minutes - preferred_overlap)
        if inside_preferred:
            preferred_status = "inside"
        elif preferred_overlap > 0:
            preferred_status = "partial"
        else:
            preferred_status = "outside"

    notes: List[str] = []
    if off_hours_minutes:
        notes.append(f"{off_hours_minutes} min outside work hours")
    elif preferred_gap_minutes:
        notes.append(f"{preferred_gap_minutes} min outside preferred hours")

    crosses_midnight = local_start.date() != local_end.date()
    if crosses_midnight:
        notes.append("crosses midnight locally")

    return ParticipantEvaluation(
        name=participant.name,
        timezone=participant.timezone_name,
        local_label=format_local_label(local_start, local_end),
        work_status=work_status,
        preferred_status=preferred_status,
        off_hours_minutes=off_hours_minutes,
        preferred_gap_minutes=preferred_gap_minutes,
        crosses_midnight=crosses_midnight,
        notes=notes,
    )


def compute_score(
    hard_conflicts: int,
    soft_conflicts: int,
    overnight_count: int,
    total_off_hours_minutes: int,
    total_preferred_gap_minutes: int,
) -> int:
    penalty = (
        hard_conflicts * 25
        + soft_conflicts * 6
        + overnight_count * 8
        + total_off_hours_minutes // 10
        + total_preferred_gap_minutes // 20
    )
    return max(0, 100 - penalty)


def evaluate_slot(
    slot_start_utc: datetime, duration_minutes: int, participants: List[Participant]
) -> SlotEvaluation:
    participant_rows = [
        participant_eval(participant, slot_start_utc, duration_minutes)
        for participant in participants
    ]
    hard_conflicts = sum(1 for row in participant_rows if row.off_hours_minutes > 0)
    soft_conflicts = sum(
        1
        for row in participant_rows
        if row.off_hours_minutes == 0
        and row.preferred_status != "not_set"
        and row.preferred_gap_minutes > 0
    )
    overnight_count = sum(1 for row in participant_rows if row.crosses_midnight)
    total_off_hours_minutes = sum(row.off_hours_minutes for row in participant_rows)
    total_preferred_gap_minutes = sum(
        row.preferred_gap_minutes for row in participant_rows
    )
    score = compute_score(
        hard_conflicts,
        soft_conflicts,
        overnight_count,
        total_off_hours_minutes,
        total_preferred_gap_minutes,
    )
    utc_end = slot_start_utc + timedelta(minutes=duration_minutes)

    return SlotEvaluation(
        utc_start=slot_start_utc.isoformat().replace("+00:00", "Z"),
        utc_end=utc_end.isoformat().replace("+00:00", "Z"),
        score=score,
        hard_conflicts=hard_conflicts,
        soft_conflicts=soft_conflicts,
        overnight_count=overnight_count,
        total_off_hours_minutes=total_off_hours_minutes,
        total_preferred_gap_minutes=total_preferred_gap_minutes,
        participants=participant_rows,
    )


def load_slots(payload: dict[str, Any], duration_minutes: int) -> List[datetime]:
    candidate_slots = payload.get("candidate_slots_utc")
    candidate_window = payload.get("candidate_window")

    if candidate_slots and candidate_window:
        raise InputError("Use either candidate_window or candidate_slots_utc, not both")
    if not candidate_slots and not candidate_window:
        raise InputError("Provide candidate_window or candidate_slots_utc")

    if candidate_slots:
        if not isinstance(candidate_slots, list) or not candidate_slots:
            raise InputError("candidate_slots_utc must be a non-empty array")
        if len(candidate_slots) > MAX_SLOTS:
            raise InputError(
                f"candidate_slots_utc exceeds {MAX_SLOTS} slots; narrow the input"
            )
        return sorted(parse_iso8601(str(item)) for item in candidate_slots)

    if not isinstance(candidate_window, dict):
        raise InputError("candidate_window must be an object")

    start = parse_iso8601(str(candidate_window.get("start", "")))
    end = parse_iso8601(str(candidate_window.get("end", "")))
    if end <= start:
        raise InputError("candidate_window.end must be later than start")

    step_minutes = candidate_window.get("step_minutes", 30)
    try:
        step_minutes = int(step_minutes)
    except (TypeError, ValueError) as exc:
        raise InputError("candidate_window.step_minutes must be an integer") from exc
    if step_minutes <= 0:
        raise InputError("candidate_window.step_minutes must be positive")

    raw_slot_count = int((end - start).total_seconds() // 60 - duration_minutes)
    slot_count = raw_slot_count // step_minutes + 1
    if slot_count <= 0:
        raise InputError(
            "candidate_window is shorter than the meeting duration; no slots to evaluate"
        )
    if slot_count > MAX_SLOTS:
        raise InputError(
            f"Search would generate {slot_count} slots, which exceeds the limit of "
            f"{MAX_SLOTS}. Narrow the window or increase step_minutes."
        )

    slots: List[datetime] = []
    current = start
    step = timedelta(minutes=step_minutes)
    duration_delta = timedelta(minutes=duration_minutes)
    while current + duration_delta <= end:
        slots.append(current)
        current += step
    return slots


def rank_slots(
    slots: List[datetime], duration_minutes: int, participants: List[Participant]
) -> List[SlotEvaluation]:
    ranked = [evaluate_slot(slot, duration_minutes, participants) for slot in slots]
    ranked.sort(
        key=lambda row: (
            row.hard_conflicts,
            row.total_off_hours_minutes,
            row.overnight_count,
            row.soft_conflicts,
            row.total_preferred_gap_minutes,
            row.utc_start,
        )
    )
    return ranked


def build_markdown(
    ranked: List[SlotEvaluation],
    participants: List[Participant],
    duration_minutes: int,
    top_n: int,
) -> str:
    inspected = len(ranked)
    best = ranked[0]
    lines: List[str] = []
    lines.append("# Meeting Window Ranking")
    lines.append("")
    lines.append(f"- Duration: {duration_minutes} minutes")
    lines.append(f"- Participants: {len(participants)}")
    lines.append(f"- Evaluated slots: {inspected}")
    lines.append(
        "- Ranking heuristic: fewer hard conflicts, fewer off-hours minutes, fewer "
        "overnight meetings, then fewer preferred-hour misses."
    )
    lines.append("")
    lines.append(
        f"Best option: `{best.utc_start}` to `{best.utc_end}` with score `{best.score}`."
    )
    if best.hard_conflicts == 0:
        lines.append("All participants are inside work hours for the top-ranked slot.")
    else:
        lines.append(
            f"The top-ranked slot still has `{best.hard_conflicts}` hard conflict(s), "
            "so this is the least-bad option rather than a perfect overlap."
        )
    lines.append("")
    lines.append("## Ranked Summary")
    lines.append("")
    lines.append(
        "| Rank | UTC Slot | Score | Hard | Soft | Overnight | Off-hours Min | Preferred-gap Min |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for index, row in enumerate(ranked[:top_n], start=1):
        lines.append(
            f"| {index} | `{row.utc_start}` -> `{row.utc_end}` | {row.score} | "
            f"{row.hard_conflicts} | {row.soft_conflicts} | {row.overnight_count} | "
            f"{row.total_off_hours_minutes} | {row.total_preferred_gap_minutes} |"
        )

    for index, row in enumerate(ranked[:top_n], start=1):
        lines.append("")
        lines.append(f"## Option {index}: `{row.utc_start}` to `{row.utc_end}`")
        lines.append("")
        lines.append(f"- Score: `{row.score}`")
        lines.append(
            f"- Hard conflicts: `{row.hard_conflicts}` | Soft conflicts: "
            f"`{row.soft_conflicts}` | Overnight: `{row.overnight_count}`"
        )
        lines.append("")
        lines.append("| Participant | Time Zone | Local Time | Work | Preferred | Notes |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for participant_row in row.participants:
            notes = ", ".join(participant_row.notes) if participant_row.notes else "ok"
            lines.append(
                f"| {participant_row.name} | `{participant_row.timezone}` | "
                f"`{participant_row.local_label}` | {participant_row.work_status} | "
                f"{participant_row.preferred_status} | {notes} |"
            )
    return "\n".join(lines)


def build_json(
    ranked: List[SlotEvaluation],
    participants: List[Participant],
    duration_minutes: int,
) -> str:
    payload = {
        "meeting_duration_minutes": duration_minutes,
        "participant_count": len(participants),
        "evaluated_slots": len(ranked),
        "ranked_slots": [asdict(row) for row in ranked],
    }
    return json.dumps(payload, indent=2)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return 1

    try:
        duration_minutes = int(payload.get("meeting_duration_minutes", 0))
    except (TypeError, ValueError):
        print("meeting_duration_minutes must be an integer", file=sys.stderr)
        return 1

    if not (1 <= duration_minutes <= MAX_DURATION_MINUTES):
        print(
            f"meeting_duration_minutes must be between 1 and {MAX_DURATION_MINUTES}",
            file=sys.stderr,
        )
        return 1

    try:
        participants = load_participants(payload)
        slots = load_slots(payload, duration_minutes)
        ranked = rank_slots(slots, duration_minutes, participants)
        top_n = int(payload.get("top_n", min(5, len(ranked))))
        top_n = max(1, min(top_n, len(ranked)))
    except (InputError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(build_json(ranked, participants, duration_minutes))
    else:
        print(build_markdown(ranked, participants, duration_minutes, top_n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
