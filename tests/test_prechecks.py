"""Pre-checks explain infeasibility in numbers before the solver is asked."""

from __future__ import annotations

from dataclasses import replace

from shule_timetable.model import Requirement, Room, School, Teacher
from shule_timetable.prechecks import run_prechecks

from .helpers import tiny_school


def codes(school: School) -> dict[str, str]:
    return {i.code: i.message for i in run_prechecks(school)}


def test_tiny_school_passes() -> None:
    assert run_prechecks(tiny_school()) == []


def test_class_needs_more_lessons_than_slots() -> None:
    school = tiny_school()
    # C1 has 4 maths + 3 chemistry; 15 maths makes 18 = exactly the 18 slots (fits), 16 does not
    for maths, fits in ((15, True), (16, False)):
        reqs = tuple(
            replace(r, lessons=maths) if r.key == ("C1", "MAT") else r for r in school.requirements
        )
        found = codes(replace(school, requirements=reqs))
        assert ("class-over-slots" in found) is (not fits)
    assert (
        "Class 1 needs 19 lessons/week but only 18 slots exist (1 too many)"
        in found["class-over-slots"]
    )


def test_teacher_over_weekly_max() -> None:
    school = tiny_school()
    t1 = Teacher("T1", "Teacher One", ("MAT",), 5, 6)
    msg = codes(replace(school, teachers={**school.teachers, "T1": t1}))["teacher-over-max"]
    assert "assigned 8 lessons/week but max_per_week is 5" in msg
    assert "Move 3 lesson(s)" in msg


def test_teacher_load_vs_availability() -> None:
    school = tiny_school()
    busy = frozenset(
        (d, p) for d in range(3) for p in range(6) if (d, p) not in {(0, 0), (0, 1), (1, 0)}
    )
    t1 = Teacher("T1", "Teacher One", ("MAT",), 18, 6, busy)
    msg = codes(replace(school, teachers={**school.teachers, "T1": t1}))[
        "teacher-over-availability"
    ]
    assert "assigned 8 lessons/week but is available in only 3 slots" in msg


def test_lab_capacity() -> None:
    school = tiny_school()
    # 12 classes' worth of lab doubles against one lab is fine; remove the lab's slots by
    # asking for more double lessons than 18 room-periods allow
    classes = dict(school.classes)
    reqs = list(school.requirements)
    from shule_timetable.model import SchoolClass

    for i in range(3, 12):
        cid = f"X{i}"
        classes[cid] = SchoolClass(cid, cid, 20, "R1")
        reqs.append(Requirement(cid, "CHE", "T2", 2, 1))
    msg = codes(replace(school, classes=classes, requirements=tuple(reqs)))["room-over-capacity"]
    assert "'lab'" in msg and "1 room(s) x 18 slots = 18" in msg


def test_subject_daily_limit() -> None:
    school = tiny_school()
    reqs = tuple(
        replace(r, lessons=7) if r.key == ("C1", "MAT") else r for r in school.requirements
    )
    msg = codes(replace(school, requirements=reqs))["subject-over-daily-limit"]
    assert "needs 7 Mathematics lessons/week but at most 2 a day over 3 days allows 6" in msg


def test_doubles_impossible_when_teacher_never_has_two_free_periods_together() -> None:
    school = tiny_school()
    # T2 is free only at P1, P4, P5 on each day: no two consecutive free periods in one segment
    free = {0, 3, 4}
    unavailable = frozenset((d, p) for d in range(3) for p in range(6) if p not in free)
    t2 = Teacher("T2", "Teacher Two", ("CHE",), 18, 6, unavailable)
    msg = codes(replace(school, teachers={**school.teachers, "T2": t2}))["doubles-impossible"]
    assert "needs 1 double Chemistry" in msg and "only 0 day(s)" in msg


def test_hall_violation_for_class_and_its_teachers() -> None:
    school = tiny_school()
    # both of C1's teachers are free only on Monday P1-P2, but C1 needs 7 lessons
    mon12 = frozenset((d, p) for d in range(3) for p in range(6) if not (d == 0 and p < 2))
    teachers = {
        "T1": replace(school.teachers["T1"], unavailable=mon12),
        "T2": replace(school.teachers["T2"], unavailable=mon12),
    }
    issues = {i.code: i.message for i in run_prechecks(replace(school, teachers=teachers))}
    # T1 is stopped earlier by the per-teacher check (8 lessons, 2 slots); the class-level
    # check is the one that names the stuck lessons
    assert "class-teacher-availability" in issues
    assert "can only go in 2 slot(s)" in issues["class-teacher-availability"]


def test_specialist_room_too_small_is_caught_by_loader_not_prechecks() -> None:
    school = tiny_school()
    rooms = {**school.rooms, "L1": Room("L1", "Lab", "lab", 40)}
    assert run_prechecks(replace(school, rooms=rooms)) == []
