"""Read and write solved timetables as JSON (human-readable day names and period labels)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .issues import InputError, Issue
from .model import Event, School, Timetable


def timetable_to_dict(school: School, timetable: Timetable) -> dict[str, Any]:
    cal = school.calendar
    return {
        "format": "shule-timetable/1",
        "school": school.name,
        "meta": timetable.meta,
        "events": [
            {
                "class": e.class_id,
                "subject": e.subject_id,
                "teacher": e.teacher_id,
                "room": e.room_id,
                "day": cal.days[e.day],
                "period": cal.periods[e.period].label,
                "length": e.length,
            }
            for e in timetable.events
        ],
    }


def save_timetable(path: str | Path, school: School, timetable: Timetable) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(timetable_to_dict(school, timetable), indent=1) + "\n", encoding="utf-8"
    )


def load_timetable(path: str | Path, school: School) -> Timetable:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise InputError([Issue("error", "bad-solution", f"cannot read {p}: {e}")]) from e
    cal = school.calendar
    events: list[Event] = []
    problems: list[Issue] = []
    for i, raw in enumerate(data.get("events", [])):
        try:
            events.append(
                Event(
                    raw["class"],
                    raw["subject"],
                    raw["teacher"],
                    raw["room"],
                    cal.day_index(raw["day"]),
                    cal.period_index(raw["period"]),
                    int(raw.get("length", 1)),
                )
            )
        except (KeyError, ValueError) as e:
            problems.append(Issue("error", "bad-solution", f"events[{i}]: {e}", str(p)))
    if problems:
        raise InputError(problems)
    return Timetable(tuple(events), dict(data.get("meta", {})))
