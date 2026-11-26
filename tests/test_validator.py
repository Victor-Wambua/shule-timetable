"""The independent validator, driven by hand-built timetables that break one rule each."""

from __future__ import annotations

from dataclasses import replace

from shule_timetable.model import Event, School, Teacher
from shule_timetable.validator import RULES, ValidationReport, validate

from .helpers import replace_event, tiny_school, valid_events, with_events


def failing(school: School, events: list[Event]) -> tuple[set[str], ValidationReport]:
    rep = validate(school, with_events(events))
    return {r.id for r in rep.rules if not r.ok}, rep


def test_hand_built_timetable_is_valid() -> None:
    rep = validate(tiny_school(), with_events(valid_events()))
    assert rep.ok, rep.violations
    assert rep.checks > 50
    assert [r.id for r in rep.rules] == [rid for rid, _ in RULES]


def test_unknown_teacher_is_not_well_formed() -> None:
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 0, teacher_id="T9"))
    assert "well-formed" in bad
    assert "unknown teacher T9" in rep.rule("well-formed").violations[0]


def test_lesson_length_three_is_not_well_formed() -> None:
    bad, _ = failing(tiny_school(), replace_event(valid_events(), 0, length=3))
    assert "well-formed" in bad


def test_period_that_does_not_exist() -> None:
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 0, period=9))
    assert "slots-exist" in bad
    assert "not a lesson period" in rep.rule("slots-exist").violations[0]


def test_blocked_slot_is_rejected() -> None:
    school = tiny_school()
    cal = replace(school.calendar, blocked=frozenset({(0, 0)}))
    bad, _ = failing(replace(school, calendar=cal), valid_events())
    assert "slots-exist" in bad


def test_missing_lesson() -> None:
    events = valid_events()[1:]
    bad, rep = failing(tiny_school(), events)
    assert "lesson-counts" in bad
    assert "has 3 Mathematics lessons, needs 4" in rep.rule("lesson-counts").violations[0]


def test_extra_lesson_for_subject_not_required() -> None:
    events = [*valid_events(), Event("C1", "CHE", "T2", "L1", 2, 4, 1)]
    bad, _ = failing(tiny_school(), events)
    assert "lesson-counts" in bad


def test_wrong_teacher_for_requirement() -> None:
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 0, teacher_id="T2"))
    assert "lesson-counts" in bad
    assert any("should be T1" in v for v in rep.rule("lesson-counts").violations)


def test_double_replaced_by_two_singles() -> None:
    events = valid_events()
    events[8:9] = [Event("C1", "CHE", "T2", "L1", 0, 2), Event("C1", "CHE", "T2", "L1", 0, 3)]
    bad, rep = failing(tiny_school(), events)
    assert "doubles" in bad and "lesson-counts" not in bad
    assert "has 0 double Chemistry" in rep.rule("doubles").violations[0]


def test_double_across_the_lunch_break() -> None:
    # period index 3 (P4) and 4 (P5) have the long break between them
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 8, period=3))
    assert "no-break-split" in bad
    assert "straddles a break" in rep.rule("no-break-split").violations[0]


def test_double_across_the_short_break_is_also_rejected() -> None:
    # P2 and P3 have the tea break between them
    bad, _ = failing(tiny_school(), replace_event(valid_events(), 8, period=1))
    assert "no-break-split" in bad


def test_class_in_two_places() -> None:
    # C1 maths moved onto C1's chemistry double
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 0, period=2))
    assert "class-clash" in bad
    assert "Class C1 is in 2 lessons" in rep.rule("class-clash").violations[0]


def test_teacher_in_two_places() -> None:
    # T1 teaches C1 at Mon P1; put C2 maths there too
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 4, period=0))
    assert "teacher-clash" in bad
    assert "Teacher T1" in rep.rule("teacher-clash").violations[0]


def test_lab_double_booked() -> None:
    # both chemistry doubles in the lab at once (also a teacher clash, which is fine)
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 10, period=2))
    assert {"room-clash", "teacher-clash"} <= bad
    assert "Room L1" in rep.rule("room-clash").violations[0]


def test_double_overlapping_the_next_lesson_in_same_room() -> None:
    # a single lab lesson placed on the second period of the other class's double
    events = valid_events()
    events[9] = Event("C1", "CHE", "T2", "L1", 0, 4, 1)  # overlaps C2's double at P5-P6
    events[8] = Event("C1", "CHE", "T2", "L1", 0, 2, 2)
    bad, _ = failing(tiny_school(), events)
    assert "room-clash" in bad


def test_teacher_teaches_while_unavailable() -> None:
    school = tiny_school()
    t1 = replace(school.teachers["T1"], unavailable=frozenset({(0, 0)}))
    school = replace(school, teachers={**school.teachers, "T1": t1})
    bad, rep = failing(school, valid_events())
    assert bad == {"teacher-availability"}
    assert "unavailable then" in rep.rule("teacher-availability").violations[0]


def test_double_in_a_classroom_instead_of_the_lab() -> None:
    bad, rep = failing(tiny_school(), replace_event(valid_events(), 8, room_id="R1"))
    assert "room-suitability" in bad
    assert "needs a lab room" in rep.rule("room-suitability").violations[0]


def test_class_too_big_for_lab() -> None:
    school = tiny_school()
    big = replace(school.classes["C1"], size=60)
    school = replace(school, classes={**school.classes, "C1": big})
    bad, rep = failing(school, valid_events())
    assert bad == {"room-suitability"}
    assert "holds 40" in rep.rule("room-suitability").violations[0]


def test_single_lesson_in_wrong_classroom() -> None:
    bad, _ = failing(tiny_school(), replace_event(valid_events(), 0, room_id="R2"))
    assert "room-suitability" in bad


def test_too_many_of_one_subject_in_a_day() -> None:
    events = valid_events()
    # C1 maths: Mon P1, Tue P1, Wed P1, Wed P2 -> move Tue P1 to Wed P5 (3 on Wednesday)
    events[1] = Event("C1", "MAT", "T1", "R1", 2, 4)
    bad, rep = failing(tiny_school(), events)
    assert "subject-per-day" in bad
    assert "has 3 Mathematics lessons on Wed (limit 2)" in rep.rule("subject-per-day").violations[0]


def test_teacher_over_weekly_maximum() -> None:
    school = tiny_school()
    t1 = Teacher("T1", "Teacher One", ("MAT",), 7, 6)
    bad, rep = failing(replace(school, teachers={**school.teachers, "T1": t1}), valid_events())
    assert bad == {"teacher-load"}
    assert "weekly maximum is 7" in rep.rule("teacher-load").violations[0]


def test_teacher_over_daily_maximum() -> None:
    school = tiny_school()
    t1 = Teacher("T1", "Teacher One", ("MAT",), 18, 1)
    bad, rep = failing(replace(school, teachers={**school.teachers, "T1": t1}), valid_events())
    assert "teacher-load" in bad
    assert any("daily maximum" in v for v in rep.rule("teacher-load").violations)


def test_every_rule_has_a_test_that_trips_it() -> None:
    """Guard: if a rule is added to RULES, someone must add a violating test."""
    assert {rid for rid, _ in RULES} == {
        "well-formed",
        "slots-exist",
        "lesson-counts",
        "doubles",
        "no-break-split",
        "class-clash",
        "teacher-clash",
        "room-clash",
        "teacher-availability",
        "room-suitability",
        "subject-per-day",
        "teacher-load",
    }
