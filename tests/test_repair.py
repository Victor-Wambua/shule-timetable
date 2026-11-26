"""Repair mode: change as few lessons as possible."""

from __future__ import annotations

from pathlib import Path

import pytest

from shule_timetable.issues import InputError
from shule_timetable.model import Teacher
from shule_timetable.repair import Change, apply_changes, count_moved, load_changes, repair
from shule_timetable.solver import SolveSettings, solve
from shule_timetable.validator import validate

from .helpers import tiny_school

S = SolveSettings(time_limit=20, workers=1)


@pytest.fixture(scope="module")
def baseline():  # type: ignore[no-untyped-def]
    school = tiny_school()
    res = solve(school, S)
    assert res.timetable is not None
    return school, res.timetable


def test_teacher_unavailable_moves_only_the_lessons_in_that_slot(baseline) -> None:  # type: ignore[no-untyped-def]
    school, old = baseline
    victim = next(e for e in old.events if e.teacher_id == "T1")
    slot = school.calendar.label((victim.day, victim.period)).replace(" ", ":")
    res = repair(school, old, [Change("unavailable", teacher="T1", slots=slot)], S)
    assert res.timetable is not None
    assert (res.moved, res.added) == (1, 0)
    assert res.minimal_proven and res.status == "OPTIMAL"
    assert validate(res.school, res.timetable).ok
    # everything else is exactly where it was
    assert count_moved(old, res.timetable) == 1
    assert res.total_lessons == old.lesson_count()


def test_whole_day_off_moves_exactly_that_days_lessons(baseline) -> None:  # type: ignore[no-untyped-def]
    school, old = baseline
    day = next(e.day for e in old.events if e.teacher_id == "T1")
    in_day = sum(e.length for e in old.events if e.teacher_id == "T1" and e.day == day)
    res = repair(
        school,
        old,
        [Change("unavailable", teacher="T1", slots=f"{school.calendar.days[day]}:*")],
        S,
    )
    assert res.timetable is not None
    assert res.moved == in_day  # the proven minimum: you cannot move fewer than those
    assert validate(res.school, res.timetable).ok


def test_teacher_leaves_and_replacement_keeps_every_slot(baseline) -> None:  # type: ignore[no-untyped-def]
    school, old = baseline
    school = school.__class__(
        **{
            **school.__dict__,
            "teachers": {**school.teachers, "T3": Teacher("T3", "Teacher Three", ("MAT",), 18, 6)},
        }
    )
    res = repair(school, old, [Change("leave", teacher="T1", to="T3")], S)
    assert res.timetable is not None
    assert res.moved == 0
    assert res.teacher_changed == 8
    assert all(e.teacher_id == "T3" for e in res.timetable.events if e.subject_id == "MAT")
    assert validate(res.school, res.timetable).ok


def test_replacement_who_is_busy_forces_some_moves(baseline) -> None:  # type: ignore[no-untyped-def]
    school, old = baseline
    # T2 (chemistry) takes over T1's maths: a clash wherever both were teaching
    res = repair(school, old, [Change("reassign", teacher="T1", to="T2")], S)
    assert res.timetable is not None
    # every period where T1 and T2 were both teaching is now a clash, and one lesson of
    # each such pair has to move: that count is the minimum
    t1 = {sl for e in old.events if e.teacher_id == "T1" for sl in e.slots}
    t2 = {sl for e in old.events if e.teacher_id == "T2" for sl in e.slots}
    assert len(t1 & t2) > 0
    assert res.moved == len(t1 & t2) and res.minimal_proven
    assert validate(res.school, res.timetable).ok


def test_added_lesson_does_not_move_anything_when_there_is_room(baseline) -> None:  # type: ignore[no-untyped-def]
    school, old = baseline
    res = repair(school, old, [Change("add_lesson", class_id="C1", subject_id="MAT", count=1)], S)
    assert res.timetable is not None
    assert (res.moved, res.added) == (0, 1)
    assert res.timetable.lesson_count() == old.lesson_count() + 1
    assert validate(res.school, res.timetable).ok


def test_repair_beats_starting_again(baseline) -> None:  # type: ignore[no-untyped-def]
    school, old = baseline
    res = repair(
        school, old, [Change("unavailable", teacher="T1", slots="Mon:*")], S, compare_scratch=True
    )
    assert res.scratch_moved is not None
    assert res.moved <= res.scratch_moved


def test_impossible_change_returns_no_timetable(baseline) -> None:  # type: ignore[no-untyped-def]
    school, old = baseline
    res = repair(school, old, [Change("unavailable", teacher="T1", slots="*:*")], S)
    assert res.timetable is None and res.status == "INFEASIBLE"


def test_apply_changes_validates_names() -> None:
    with pytest.raises(InputError, match="teacher 'T9' not found"):
        apply_changes(tiny_school(), [Change("unavailable", teacher="T9", slots="Mon:P1")])
    with pytest.raises(InputError, match="unknown period"):
        apply_changes(tiny_school(), [Change("unavailable", teacher="T1", slots="Mon:P99")])


def test_set_max_per_week_and_leave_marks_teacher_unavailable() -> None:
    school = apply_changes(tiny_school(), [Change("set_max_per_week", teacher="T1", value=25)])
    assert school.teachers["T1"].max_per_week == 25
    gone = apply_changes(
        school.__class__(
            **{
                **school.__dict__,
                "teachers": {**school.teachers, "T3": Teacher("T3", "Three", ("MAT",), 18, 6)},
            }
        ),
        [Change("leave", teacher="T1", to="T3")],
    )
    assert len(gone.teachers["T1"].unavailable) == len(gone.calendar.days) * len(
        gone.calendar.periods
    )
    assert {r.teacher_id for r in gone.requirements if r.subject_id == "MAT"} == {"T3"}


def test_load_changes_yaml(tmp_path: Path) -> None:
    f = tmp_path / "c.yaml"
    f.write_text(
        "changes:\n"
        "  - unavailable: {teacher: T1, slots: 'Mon:P1-P2'}\n"
        "  - leave: {teacher: T2, replacement: T3}\n"
        "  - add_lesson: {class: C1, subject: MAT, count: 2}\n"
        "  - reassign: {from: T1, to: T3, class: C1}\n"
        "  - set_max_per_week: {teacher: T3, value: 30}\n"
    )
    kinds = [c.kind for c in load_changes(f)]
    assert kinds == ["unavailable", "leave", "add_lesson", "reassign", "set_max_per_week"]
    assert load_changes(f)[0].describe() == "Teacher T1 becomes unavailable Mon:P1-P2"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("changes: []", "expected a 'changes:' list"),
        ("changes:\n  - fly: {x: 1}", "unknown change 'fly'"),
        ("changes:\n  - unavailable: {teacher: T1}", "is missing slots"),
        ("changes:\n  - unavailable: {teacher: T1, slots: x}\n    leave: {}", "single-key mapping"),
    ],
)
def test_load_changes_errors(tmp_path: Path, body: str, message: str) -> None:
    f = tmp_path / "c.yaml"
    f.write_text(body)
    with pytest.raises(InputError, match=message):
        load_changes(f)
