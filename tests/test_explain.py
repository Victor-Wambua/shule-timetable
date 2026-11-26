from __future__ import annotations

from dataclasses import replace

from shule_timetable.explain import binding_constraints, explain_infeasible
from shule_timetable.model import (
    Requirement,
    Room,
    School,
    SchoolClass,
    Subject,
    Teacher,
    Weights,
)
from shule_timetable.prechecks import run_prechecks
from shule_timetable.solver import SolveSettings, solve

from .helpers import calendar, tiny_school


def lab_pigeonhole() -> School:
    """Two teachers who are only free for one shared double period, and one lab.

    Each teacher alone is fine, the lab alone is fine, so every pre-check passes; only the
    three together are impossible.
    """
    only_mon_p5_p6 = frozenset(
        (d, p) for d in range(3) for p in range(6) if (d, p) not in {(0, 4), (0, 5)}
    )
    return School(
        "Pigeonhole",
        calendar(),
        {"CHE": Subject("CHE", "Chemistry", "lab", "doubles", doubles=1)},
        {
            "T2": Teacher("T2", "Teacher Two", ("CHE",), 18, 6, only_mon_p5_p6),
            "T3": Teacher("T3", "Teacher Three", ("CHE",), 18, 6, only_mon_p5_p6),
        },
        {
            "R1": Room("R1", "Room 1", "classroom", 40),
            "R2": Room("R2", "Room 2", "classroom", 40),
            "L1": Room("L1", "Chemistry Lab", "lab", 40),
        },
        {
            "C1": SchoolClass("C1", "Class 1", 30, "R1"),
            "C2": SchoolClass("C2", "Class 2", 30, "R2"),
        },
        (Requirement("C1", "CHE", "T2", 2, 1), Requirement("C2", "CHE", "T3", 2, 1)),
        weights=Weights(),
    )


def test_prechecks_cannot_see_the_pigeonhole_but_the_solver_proves_it() -> None:
    school = lab_pigeonhole()
    assert run_prechecks(school) == []
    assert solve(school, SolveSettings(time_limit=10, workers=1)).status == "INFEASIBLE"


def test_unsat_core_names_the_conflicting_rules_in_plain_english() -> None:
    exp = explain_infeasible(lab_pigeonhole(), time_limit=20, shrink_time=10, workers=1)
    assert exp.status == "infeasible"
    groups = {c.group for c in exp.core}
    # the lab, both teachers' availability and the two lesson requirements are all needed
    assert groups == {
        "teacher-avail:T2",
        "teacher-avail:T3",
        "rooms:lab",
        "req:C1:CHE",
        "req:C2:CHE",
    }
    assert exp.minimal
    text = exp.render()
    assert "cannot all hold together (minimal conflicting set)" in text
    assert "Teacher T2 (Teacher Two) is unavailable" in text
    assert "Each lab room (Chemistry Lab) hosts one class at a time" in text
    assert "Class Class 1 must get 2 Chemistry lessons a week, 1 of them as double lessons" in text
    assert "Ways out" in text


def test_core_is_minimal_every_member_is_needed() -> None:
    """Dropping any one rule from the core must make the rest satisfiable."""
    school = lab_pigeonhole()
    exp = explain_infeasible(school, workers=1)
    # relax each rule in turn by removing what it protects, and re-solve
    relaxed = {
        "teacher-avail:T2": replace(
            school,
            teachers={
                **school.teachers,
                "T2": replace(school.teachers["T2"], unavailable=frozenset()),
            },
        ),
        "teacher-avail:T3": replace(
            school,
            teachers={
                **school.teachers,
                "T3": replace(school.teachers["T3"], unavailable=frozenset()),
            },
        ),
        "rooms:lab": replace(school, rooms={**school.rooms, "L2": Room("L2", "Lab 2", "lab", 40)}),
        "req:C1:CHE": replace(school, requirements=(school.requirements[1],)),
        "req:C2:CHE": replace(school, requirements=(school.requirements[0],)),
    }
    assert {c.group for c in exp.core} == set(relaxed)
    for group, variant in relaxed.items():
        assert solve(variant, SolveSettings(time_limit=10, workers=1)).timetable is not None, group


def test_feasible_school_is_reported_feasible() -> None:
    exp = explain_infeasible(tiny_school(), workers=1)
    assert exp.status == "feasible" and "A timetable exists" in exp.render()


def test_explain_includes_precheck_messages() -> None:
    school = tiny_school()
    t1 = replace(school.teachers["T1"], max_per_week=5)
    exp = explain_infeasible(
        replace(school, teachers={**school.teachers, "T1": t1}), time_limit=10, workers=1
    )
    assert exp.status == "infeasible"
    assert any("max_per_week is 5" in str(i) for i in exp.prechecks)
    assert any(c.group == "teacher-load:T1" for c in exp.core)


def test_binding_constraints_name_the_full_resources() -> None:
    school = tiny_school()
    res = solve(school, SolveSettings(time_limit=10, workers=1))
    assert res.timetable is not None
    bound = binding_constraints(school, res.timetable, threshold=0.2)
    kinds = {b.kind for b in bound}
    assert "teacher" in kinds and "room-type" in kinds
    t1 = next(b for b in bound if b.entity == "T1")
    assert (t1.used, t1.available) == (8, 18) and "8 of 18" in t1.text
    assert bound == sorted(bound, key=lambda b: -b.utilisation)
