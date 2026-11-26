"""CSV export: one row per lesson event."""

from __future__ import annotations

import csv
import io

from ..model import School, Timetable

HEADER = [
    "class",
    "subject",
    "teacher",
    "room",
    "day",
    "first_period",
    "start",
    "end",
    "periods",
]


def timetable_csv(school: School, timetable: Timetable) -> str:
    cal = school.calendar
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER)
    for e in sorted(timetable.events, key=lambda e: (e.class_id, e.day, e.period)):
        w.writerow(
            [
                school.classes[e.class_id].name,
                school.subjects[e.subject_id].name,
                school.teachers[e.teacher_id].name,
                school.rooms[e.room_id].name,
                cal.days[e.day],
                cal.periods[e.period].label,
                cal.periods[e.period].start,
                cal.periods[e.period + e.length - 1].end,
                e.length,
            ]
        )
    return buf.getvalue()
