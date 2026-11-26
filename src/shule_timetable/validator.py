"""Independent validator: re-checks every hard constraint on a finished timetable.

This module deliberately knows nothing about the solver. It reads only the input model
and the list of lesson events, and walks them with plain loops. If the solver model has a
bug, this is the thing that catches it, and it is the source of the tick marks in the
published pages.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .model import HOME, School, Slot, Timetable


@dataclass
class RuleResult:
    id: str
    title: str
    checked: int = 0
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


@dataclass
class ValidationReport:
    rules: list[RuleResult]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.rules)

    @property
    def violations(self) -> list[str]:
        return [v for r in self.rules for v in r.violations]

    @property
    def checks(self) -> int:
        return sum(r.checked for r in self.rules)

    def rule(self, rule_id: str) -> RuleResult:
        return next(r for r in self.rules if r.id == rule_id)


RULES = [
    ("well-formed", "Every lesson refers to a real class, subject, teacher and room"),
    ("slots-exist", "Lessons only use periods that exist (not blocked, not past a short day)"),
    (
        "lesson-counts",
        "Every class gets exactly the required lessons per subject, with its teacher",
    ),
    ("doubles", "Required double lessons are two consecutive periods"),
    ("no-break-split", "No double lesson is split across a break"),
    ("class-clash", "No class is in two places at once"),
    ("teacher-clash", "No teacher is in two places at once"),
    ("room-clash", "No room is double-booked"),
    ("teacher-availability", "Teachers only teach when they are available"),
    ("room-suitability", "Specialist lessons are in a room of the right type and size"),
    ("subject-per-day", "No class has more of one subject in a day than the limit"),
    ("teacher-load", "Teachers stay within their weekly and daily maximum"),
]


def validate(school: School, timetable: Timetable) -> ValidationReport:
    res = {rid: RuleResult(rid, title) for rid, title in RULES}
    cal = school.calendar

    def bad(rid: str, msg: str) -> None:
        res[rid].violations.append(msg)

    # -- well-formed ------------------------------------------------------
    sound = []
    for e in timetable.events:
        res["well-formed"].checked += 1
        problems = []
        if e.class_id not in school.classes:
            problems.append(f"unknown class {e.class_id}")
        if e.subject_id not in school.subjects:
            problems.append(f"unknown subject {e.subject_id}")
        if e.teacher_id not in school.teachers:
            problems.append(f"unknown teacher {e.teacher_id}")
        if e.room_id not in school.rooms:
            problems.append(f"unknown room {e.room_id}")
        if e.length not in (1, 2):
            problems.append(f"lesson length {e.length} (must be 1 or 2)")
        if problems:
            bad("well-formed", f"{e.class_id} {e.subject_id}: {'; '.join(problems)}")
        else:
            sound.append(e)

    # -- slots exist --------------------------------------------------------
    placed = []
    for e in sound:
        res["slots-exist"].checked += 1
        missing = [s for s in e.slots if not cal.is_valid(s)]
        if missing:
            where = ", ".join(_name(school, s) for s in missing)
            bad(
                "slots-exist",
                f"{e.class_id} {e.subject_id} uses {where}, which is not a lesson period",
            )
        else:
            placed.append(e)

    # -- lesson counts and doubles -----------------------------------------
    per_req_periods: Counter[tuple[str, str]] = Counter()
    per_req_doubles: Counter[tuple[str, str]] = Counter()
    for e in sound:
        per_req_periods[(e.class_id, e.subject_id)] += e.length
        if e.length == 2:
            per_req_doubles[(e.class_id, e.subject_id)] += 1
    required = {r.key: r for r in school.requirements}
    for key, r in required.items():
        res["lesson-counts"].checked += 1
        got = per_req_periods.get(key, 0)
        if got != r.lessons:
            bad(
                "lesson-counts",
                f"Class {r.class_id} has {got} {school.subjects[r.subject_id].name} lessons, "
                f"needs {r.lessons}",
            )
        res["doubles"].checked += 1
        gd = per_req_doubles.get(key, 0)
        if gd != r.doubles:
            bad(
                "doubles",
                f"Class {r.class_id} has {gd} double {school.subjects[r.subject_id].name} "
                f"lesson(s), needs {r.doubles}",
            )
    for e in sound:
        res["lesson-counts"].checked += 1
        want = required.get((e.class_id, e.subject_id))
        if want is None:
            bad(
                "lesson-counts",
                f"Class {e.class_id} has {school.subjects[e.subject_id].name} scheduled "
                "but does not need it",
            )
        elif e.teacher_id != want.teacher_id:
            bad(
                "lesson-counts",
                f"Class {e.class_id} {school.subjects[e.subject_id].name} is taught by "
                f"{e.teacher_id} but should be {want.teacher_id}",
            )

    # -- doubles do not straddle breaks ----------------------------------------
    for e in sound:
        if e.length == 2:
            res["no-break-split"].checked += 1
            if cal.break_between(e.period, e.period + 1):
                bad(
                    "no-break-split",
                    f"Class {e.class_id} {school.subjects[e.subject_id].name} double on "
                    f"{_name(school, (e.day, e.period))} straddles a break",
                )

    # -- clashes -----------------------------------------------------------------
    for rid, attr, noun in (
        ("class-clash", "class_id", "Class"),
        ("teacher-clash", "teacher_id", "Teacher"),
        ("room-clash", "room_id", "Room"),
    ):
        occupant: dict[tuple[str, Slot], list[str]] = defaultdict(list)
        for e in sound:
            for s in e.slots:
                occupant[(getattr(e, attr), s)].append(f"{e.class_id} {e.subject_id}")
        res[rid].checked = len(occupant)
        for (who, s), lessons in sorted(occupant.items()):
            if len(lessons) > 1:
                bad(
                    rid,
                    f"{noun} {who} is in {len(lessons)} lessons at {_name(school, s)}: "
                    + " and ".join(lessons),
                )

    # -- teacher availability ------------------------------------------------
    for e in sound:
        t = school.teachers.get(e.teacher_id)
        if t is None:
            continue
        for s in e.slots:
            res["teacher-availability"].checked += 1
            if s in t.unavailable:
                bad(
                    "teacher-availability",
                    f"Teacher {t.id} teaches Class {e.class_id} at {_name(school, s)} "
                    "but is unavailable then",
                )

    # -- room suitability ----------------------------------------------------------
    for e in sound:
        res["room-suitability"].checked += 1
        needed = required.get((e.class_id, e.subject_id))
        if needed is None:
            continue
        subject = school.subjects[needed.subject_id]
        klass = school.classes[e.class_id]
        room = school.rooms[e.room_id]
        in_pool = subject.room_type != HOME and (subject.room_use == "all" or e.length == 2)
        if in_pool:
            if room.type != subject.room_type:
                bad(
                    "room-suitability",
                    f"{subject.name} for Class {e.class_id} is in {room.name} "
                    f"(type {room.type}); needs a {subject.room_type} room",
                )
            elif room.capacity < klass.size:
                bad(
                    "room-suitability",
                    f"Class {e.class_id} ({klass.size} learners) is in {room.name}, "
                    f"which holds {room.capacity}",
                )
        elif e.room_id != klass.home_room:
            bad(
                "room-suitability",
                f"{subject.name} for Class {e.class_id} should be in its own classroom "
                f"{klass.home_room}, not {room.name}",
            )

    # -- subject per day -------------------------------------------------------------
    per_day: Counter[tuple[str, str, int]] = Counter()
    for e in sound:
        per_day[(e.class_id, e.subject_id, e.day)] += e.length
    for key in required:
        limit = school.subject_max_per_day(key[1])
        for d in range(len(cal.days)):
            res["subject-per-day"].checked += 1
            n = per_day.get((key[0], key[1], d), 0)
            if n > limit:
                bad(
                    "subject-per-day",
                    f"Class {key[0]} has {n} {school.subjects[key[1]].name} lessons on "
                    f"{cal.days[d]} (limit {limit})",
                )

    # -- teacher load ------------------------------------------------------------------
    week: Counter[str] = Counter()
    day: Counter[tuple[str, int]] = Counter()
    for e in sound:
        week[e.teacher_id] += e.length
        day[(e.teacher_id, e.day)] += e.length
    for tid, t in school.teachers.items():
        res["teacher-load"].checked += 1
        if week.get(tid, 0) > t.max_per_week:
            bad(
                "teacher-load",
                f"Teacher {tid} has {week[tid]} lessons; weekly maximum is {t.max_per_week}",
            )
        for d in range(len(cal.days)):
            res["teacher-load"].checked += 1
            if day.get((tid, d), 0) > t.max_per_day:
                bad(
                    "teacher-load",
                    f"Teacher {tid} has {day[(tid, d)]} lessons on {cal.days[d]}; daily "
                    f"maximum is {t.max_per_day}",
                )
    return ValidationReport(list(res.values()))


def _name(school: School, slot: Slot) -> str:
    d, p = slot
    if 0 <= d < len(school.calendar.days) and 0 <= p < len(school.calendar.periods):
        return school.calendar.label(slot)
    return f"day {d} period {p}"
