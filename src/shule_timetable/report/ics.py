"""iCalendar export: one weekly-recurring event per lesson, times converted to UTC."""

from __future__ import annotations

import datetime as dt

from ..model import Event, School, Term

# East Africa Time has no daylight saving, so a fixed +3h offset is exact for Nairobi.
EAT = dt.timedelta(hours=3)
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
STAMP = "20260101T000000Z"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """Fold to 75 octets per RFC 5545 (continuation lines start with a space)."""
    out: list[str] = []
    cur = ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > (75 if not out else 74):
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return [out[0], *[" " + x for x in out[1:]]]


def _weekday(name: str) -> int | None:
    key = name[:3].lower()
    return WEEKDAYS.index(key) if key in WEEKDAYS else None


def _first_date(term_start: dt.date, weekday: int) -> dt.date:
    return term_start + dt.timedelta(days=(weekday - term_start.weekday()) % 7)


def supports_ics(school: School) -> bool:
    return all(_weekday(d) is not None for d in school.calendar.days)


def build_ics(school: School, events: list[Event], title: str, perspective: str) -> str:
    """``perspective`` is 'teacher', 'class' or 'room': what the summary should name."""
    term = school.term or Term(dt.date(2026, 1, 5), 13)
    cal = school.calendar
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Shule Timetable//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_esc(title)}",
        "X-WR-TIMEZONE:Africa/Nairobi",
    ]
    for e in events:
        wd = _weekday(cal.days[e.day])
        if wd is None:
            continue
        day = _first_date(term.start, wd)
        start = _parse(cal.periods[e.period].start)
        end = _parse(cal.periods[e.period + e.length - 1].end)
        dtstart = dt.datetime.combine(day, start) - EAT
        dtend = dt.datetime.combine(day, end) - EAT
        subject = school.subjects[e.subject_id].name
        klass = school.classes[e.class_id].name
        room = school.rooms[e.room_id].name
        teacher = school.teachers[e.teacher_id].name
        if perspective == "teacher":
            summary, desc = f"{subject} - {klass}", f"Teacher: {teacher}"
        elif perspective == "class":
            summary, desc = f"{subject} ({teacher})", f"Class: {klass}"
        else:
            summary, desc = f"{subject} - {klass}", f"Teacher: {teacher}"
        uid = (
            f"{perspective}-{title}-{e.class_id}-{e.subject_id}-{e.day}-{e.period}@shule-timetable"
        )
        body = [
            "BEGIN:VEVENT",
            f"UID:{_esc(uid.replace(' ', '_'))}",
            f"DTSTAMP:{STAMP}",
            f"DTSTART:{dtstart:%Y%m%dT%H%M%S}Z",
            f"DTEND:{dtend:%Y%m%dT%H%M%S}Z",
            f"RRULE:FREQ=WEEKLY;COUNT={term.weeks}",
            f"SUMMARY:{_esc(summary)}",
            f"LOCATION:{_esc(room)}",
            f"DESCRIPTION:{_esc(desc)}",
            "END:VEVENT",
        ]
        lines.extend(body)
    lines.append("END:VCALENDAR")
    folded: list[str] = []
    for ln in lines:
        folded.extend(_fold(ln))
    return "\r\n".join(folded) + "\r\n"


def _parse(hhmm: str) -> dt.time:
    h, m = hhmm.split(":")
    return dt.time(int(h), int(m))
