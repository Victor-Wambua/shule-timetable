"""Shared fixtures: a tiny hand-checkable school and a hand-built valid timetable."""

from __future__ import annotations

from dataclasses import replace

from shule_timetable.model import (
    Break,
    Calendar,
    Event,
    Period,
    Requirement,
    Room,
    School,
    SchoolClass,
    Subject,
    Teacher,
    Timetable,
    Weights,
)

ZERO = Weights(0, 0, 0, 0, 0, 0, 0, 0, 0)


def calendar(days: int = 3, periods: int = 6) -> Calendar:
    names = ("Mon", "Tue", "Wed", "Thu", "Fri")[:days]
    pers = tuple(Period(f"P{i + 1}", f"{8 + i}:00", f"{8 + i}:40") for i in range(periods))
    # tea after P2 (short), lunch after P4 (long): segments P1-P2, P3-P4, P5-P6
    return Calendar(names, pers, (Break(1, "Tea"), Break(3, "Lunch", True)))


def tiny_school(weights: Weights | None = None) -> School:
    subjects = {
        "MAT": Subject("MAT", "Mathematics", heavy=True),
        "CHE": Subject("CHE", "Chemistry", "lab", "doubles", doubles=1),
    }
    teachers = {
        "T1": Teacher("T1", "Teacher One", ("MAT",), 18, 6),
        "T2": Teacher("T2", "Teacher Two", ("CHE",), 18, 6),
    }
    rooms = {
        "R1": Room("R1", "Room 1", "classroom", 40),
        "R2": Room("R2", "Room 2", "classroom", 40),
        "L1": Room("L1", "Lab", "lab", 40),
    }
    classes = {
        "C1": SchoolClass("C1", "Class 1", 30, "R1"),
        "C2": SchoolClass("C2", "Class 2", 30, "R2"),
    }
    reqs = (
        Requirement("C1", "MAT", "T1", 4),
        Requirement("C2", "MAT", "T1", 4),
        Requirement("C1", "CHE", "T2", 3, 1),
        Requirement("C2", "CHE", "T2", 3, 1),
    )
    return School(
        "Tiny",
        calendar(),
        subjects,
        teachers,
        rooms,
        classes,
        reqs,
        weights=weights or Weights(),
    )


def valid_events() -> list[Event]:
    """A timetable for tiny_school() worked out by hand. days: Mon=0 Tue=1 Wed=2; P1=0..."""
    return [
        # C1 maths (T1): Mon P1, Tue P1, Wed P1, Wed P2
        Event("C1", "MAT", "T1", "R1", 0, 0),
        Event("C1", "MAT", "T1", "R1", 1, 0),
        Event("C1", "MAT", "T1", "R1", 2, 0),
        Event("C1", "MAT", "T1", "R1", 2, 1),
        # C2 maths (T1): Mon P2, Tue P2, Wed P3, Wed P4
        Event("C2", "MAT", "T1", "R2", 0, 1),
        Event("C2", "MAT", "T1", "R2", 1, 1),
        Event("C2", "MAT", "T1", "R2", 2, 2),
        Event("C2", "MAT", "T1", "R2", 2, 3),
        # C1 chemistry (T2): double Mon P3-P4 in the lab, single Tue P3 at home
        Event("C1", "CHE", "T2", "L1", 0, 2, 2),
        Event("C1", "CHE", "T2", "R1", 1, 2),
        # C2 chemistry (T2): double Mon P5-P6 in the lab, single Tue P5 at home
        Event("C2", "CHE", "T2", "L1", 0, 4, 2),
        Event("C2", "CHE", "T2", "R2", 1, 4),
    ]


def valid_timetable() -> Timetable:
    return Timetable(tuple(valid_events()))


def with_events(events: list[Event]) -> Timetable:
    return Timetable(tuple(events))


def replace_event(events: list[Event], index: int, **changes: object) -> list[Event]:
    out = list(events)
    out[index] = replace(out[index], **changes)  # type: ignore[arg-type]
    return out


def mini_school(
    lessons: list[tuple[str, str, str, int]],
    *,
    unavailable: dict[str, frozenset[tuple[int, int]]] | None = None,
    weights: Weights | None = None,
    heavy: bool = False,
    max_per_day: int = 2,
    morning_until: int | None = None,
    teacher_max_day: int = 6,
) -> School:
    """lessons = [(class, subject, teacher, count)], every subject in a home classroom."""
    from shule_timetable.model import Limits

    unavailable = unavailable or {}
    sids = sorted({sub for _, sub, _, _ in lessons})
    subjects = {s: Subject(s, s, heavy=heavy) for s in sids}
    tids = sorted({t for _, _, t, _ in lessons})
    teachers = {
        t: Teacher(t, t, tuple(sids), 30, teacher_max_day, unavailable.get(t, frozenset()))
        for t in tids
    }
    cids = sorted({c for c, _, _, _ in lessons})
    rooms = {f"R{c}": Room(f"R{c}", f"R{c}", "classroom", 40) for c in cids}
    classes = {c: SchoolClass(c, c, 30, f"R{c}") for c in cids}
    reqs = tuple(Requirement(c, s, t, n) for c, s, t, n in lessons)
    from dataclasses import replace as _r

    return _r(
        School(
            "Mini", calendar(), subjects, teachers, rooms, classes, reqs, weights=weights or ZERO
        ),
        limits=Limits(max_per_subject_per_day=max_per_day, morning_until=morning_until),
    )


TINY_FILES = {
    "school.yaml": """name: Tiny Test School
synthetic: true
days: [Mon, Tue, Wed]
periods:
  - {label: P1, start: "08:00", end: "08:40"}
  - {label: P2, start: "08:40", end: "09:20"}
  - {label: P3, start: "09:40", end: "10:20"}
  - {label: P4, start: "10:20", end: "11:00"}
  - {label: P5, start: "11:20", end: "12:00"}
  - {label: P6, start: "12:00", end: "12:40"}
breaks:
  - {after: P2, name: Tea}
  - {after: P4, name: Lunch, long: true}
""",
    "subjects.csv": "id,name,room_type,room_use,doubles,heavy,avoid_edges\n"
    "MAT,Mathematics,home,all,0,yes,no\n"
    "CHE,Chemistry,lab,doubles,1,no,no\n",
    "rooms.csv": "id,name,type,capacity\nR1,Room 1,classroom,40\nR2,Room 2,classroom,40\nL1,Lab,lab,40\n",
    "classes.csv": "id,name,size,home_room\nC1,Class 1,30,R1\nC2,Class 2,30,R2\n",
    "teachers.csv": "id,name,subjects,max_per_week,max_per_day,unavailable\n"
    "T1,Teacher One,MAT,18,6,\nT2,Teacher Two,CHE,18,6,\n",
    "requirements.csv": "class,subject,teacher,lessons,doubles\n"
    "C1,MAT,T1,4,0\nC2,MAT,T1,4,0\nC1,CHE,T2,3,1\nC2,CHE,T2,3,1\n",
}
