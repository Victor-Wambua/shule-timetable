"""Solver behaviour on small instances whose optimum can be worked out by hand."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from shule_timetable.model import Requirement, Weights
from shule_timetable.scoring import score
from shule_timetable.solver import SolveSettings, solve
from shule_timetable.validator import validate

from .helpers import ZERO, calendar, mini_school, tiny_school

FAST = SolveSettings(time_limit=20, workers=1, seed=1)
ALL_DAY = [(d, p) for d in range(3) for p in range(6)]


def only(**kw: int) -> Weights:
    return replace(ZERO, **kw)


def free_only(*slots: tuple[int, int]) -> frozenset[tuple[int, int]]:
    return frozenset(s for s in ALL_DAY if s not in slots)


def test_tiny_school_solves_and_passes_the_independent_validator() -> None:
    school = tiny_school()
    res = solve(school, FAST)
    assert res.status == "OPTIMAL"
    assert res.timetable is not None
    rep = validate(school, res.timetable)
    assert rep.ok, rep.violations
    assert res.timetable.lesson_count() == sum(r.lessons for r in school.requirements)


def test_solver_objective_equals_independent_python_score() -> None:
    school = tiny_school()
    res = solve(school, FAST)
    assert res.status == "OPTIMAL"
    assert res.breakdown is not None
    assert res.objective == res.breakdown.total


def test_deterministic_with_fixed_seed_and_one_worker() -> None:
    school = tiny_school()
    a = solve(school, FAST)
    b = solve(school, FAST)
    assert a.timetable is not None and b.timetable is not None
    assert a.timetable.events == b.timetable.events


def test_gap_is_zero_when_optimal() -> None:
    res = solve(tiny_school(), FAST)
    assert res.gap == 0.0 and res.best_bound == res.objective


def test_hard_only_mode_reports_zero_objective() -> None:
    res = solve(tiny_school(), replace(FAST, soft=False))
    assert res.timetable is not None and res.objective == 0
    assert validate(tiny_school(), res.timetable).ok


def test_infeasible_instance_is_reported() -> None:
    # 3 maths lessons for one class but a teacher free in only two slots
    school = mini_school([("A", "MAT", "T", 3)], unavailable={"T": free_only((0, 0), (1, 0))})
    res = solve(school, FAST)
    assert res.status == "INFEASIBLE" and res.timetable is None


def test_double_lesson_never_straddles_a_break() -> None:
    school = tiny_school()
    res = solve(school, FAST)
    assert res.timetable is not None
    for e in res.timetable.events:
        if e.length == 2:
            assert not school.calendar.break_between(e.period, e.period + 1)


def test_specialist_double_uses_the_lab_and_theory_uses_the_classroom() -> None:
    school = tiny_school()
    res = solve(school, FAST)
    assert res.timetable is not None
    for e in res.timetable.events:
        if e.subject_id == "CHE":
            assert (e.room_id == "L1") == (e.length == 2)


# ---- optimal objectives worked out by hand ---------------------------------------------
def test_optimum_days_compact_is_one() -> None:
    # 3 lessons, at most 1 per day -> teacher must come in 3 days. With 6 lessons a day
    # allowed the fewest days would be ceil(3/6)=1, so exactly 2 extra days... but the daily
    # cap used is min(max_per_day=2, longest day) so the floor is ceil(3/2)=2 and excess is 1.
    school = mini_school(
        [("A", "MAT", "T", 3)],
        weights=only(teacher_days_compact=1),
        max_per_day=1,
        teacher_max_day=2,
    )
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 1
    assert score(school, res.timetable).total == 1  # type: ignore[arg-type]


def test_optimum_heavy_subject_forced_into_the_afternoon() -> None:
    # teacher is only free P3-P6 (index 2-5); mornings end after P2 -> both lessons are late
    school = mini_school(
        [("A", "MAT", "T", 2)],
        unavailable={"T": free_only(*[(d, p) for d in range(3) for p in range(2, 6)])},
        weights=only(heavy_morning=3),
        heavy=True,
        morning_until=1,
    )
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 6


def test_optimum_teacher_gap_is_two_idle_periods() -> None:
    # T is free only at Mon P1 and Mon P4 and teaches two classes once each: P2, P3 idle
    school = mini_school(
        [("A", "MAT", "T", 1), ("B", "MAT", "T", 1)],
        unavailable={"T": free_only((0, 0), (0, 3))},
        weights=only(teacher_gaps=2),
    )
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 4


def test_optimum_class_gap() -> None:
    school = mini_school(
        [("A", "MAT", "T1", 1), ("A", "ENG", "T2", 1)],
        unavailable={"T1": free_only((0, 0)), "T2": free_only((0, 3))},
        weights=only(class_gaps=8),
    )
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 16


def test_optimum_four_in_a_row_costs_one_window() -> None:
    # T teaches four classes once each, free only Mon P1-P4: one window of 4 in a row
    school = mini_school(
        [(c, "MAT", "T", 1) for c in "ABCD"],
        unavailable={"T": free_only(*[(0, p) for p in range(4)])},
        weights=only(teacher_consecutive=6),
    )
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 6


def test_long_break_resets_the_back_to_back_count() -> None:
    # free at P3,P4 (before the long break after P4) and P5,P6 (after): 4 lessons, but the
    # lunch break splits them, so no window of 4 exists
    school = mini_school(
        [(c, "MAT", "T", 1) for c in "ABCD"],
        unavailable={"T": free_only(*[(0, p) for p in range(2, 6)])},
        weights=only(teacher_consecutive=6),
    )
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 0


def test_spread_pushes_lessons_onto_different_days() -> None:
    school = mini_school([("A", "MAT", "T", 3)], weights=only(spread_subjects=4))
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 0
    assert res.timetable is not None
    assert len({e.day for e in res.timetable.events}) == 3


def test_spread_penalty_when_days_are_unavailable() -> None:
    # teacher free only on Mon and Tue: 3 lessons use at most 2 days -> 1 day short, 4 points
    school = mini_school(
        [("A", "MAT", "T", 3)],
        unavailable={"T": frozenset((2, p) for p in range(6))},
        weights=only(spread_subjects=4),
    )
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 4


def test_balance_penalises_a_heavy_day() -> None:
    # 4 lessons over 3 days: ideal share ceil(4/3)=2, so a 3-lesson day costs 1
    school = mini_school(
        [
            ("A", "MAT", "T1", 1),
            ("A", "ENG", "T2", 1),
            ("A", "SCI", "T3", 1),
            ("A", "ART", "T4", 1),
        ],
        unavailable={t: frozenset(s for s in ALL_DAY if s[0] != 0) for t in ("T1", "T2", "T3")},
        weights=only(balance_daily_load=2),
    )
    # T1-T3 are only free Monday, so Monday carries at least 3 lessons: over by 1 -> 2 points
    res = solve(school, FAST)
    assert res.status == "OPTIMAL" and res.objective == 2


def test_weight_zero_switches_a_rule_off() -> None:
    def run(weight: int) -> float | None:
        school = mini_school(
            [("A", "MAT", "T", 1), ("B", "MAT", "T", 1)],
            unavailable={"T": free_only((0, 0), (0, 3))},
            weights=only(teacher_gaps=weight),
        )
        return solve(school, FAST).objective

    assert run(2) == 4 and run(0) == 0


# ---- property test: anything the solver returns must pass the independent validator -------
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    n_classes=st.integers(1, 3),
    n_teachers=st.integers(1, 3),
    lessons=st.lists(st.integers(1, 4), min_size=1, max_size=6),
    free_cut=st.lists(st.integers(0, 17), max_size=6),
    seed=st.integers(0, 5),
)
def test_any_solution_returned_passes_the_validator(
    n_classes: int, n_teachers: int, lessons: list[int], free_cut: list[int], seed: int
) -> None:
    specs = []
    for i, n in enumerate(lessons):
        specs.append((f"C{i % n_classes}", f"S{i}", f"T{i % n_teachers}", n))
    blocked = frozenset(ALL_DAY[i] for i in free_cut)
    school = mini_school(specs, unavailable={"T0": blocked}, weights=Weights())
    res = solve(school, SolveSettings(time_limit=10, workers=1, seed=seed))
    assert res.status in {"OPTIMAL", "FEASIBLE", "INFEASIBLE"}
    if res.timetable is not None:
        rep = validate(school, res.timetable)
        assert rep.ok, rep.violations
        assert res.timetable.lesson_count() == sum(n for *_, n in specs)
        if res.status == "OPTIMAL":
            assert res.objective == score(school, res.timetable).total


def test_requirement_blocks_property() -> None:
    assert Requirement("A", "B", "C", 5, 2).blocks == 3
    assert calendar().slots  # keep helper import honest


@pytest.mark.slow
def test_primary_sample_is_solved_and_valid() -> None:
    import tempfile
    from pathlib import Path

    from shule_timetable.demo import generate_primary, write_inputs
    from shule_timetable.loader import load_school

    with tempfile.TemporaryDirectory() as d:
        write_inputs(generate_primary(), Path(d))
        school = load_school(d)
    res = solve(school, SolveSettings(time_limit=8, workers=1))
    assert res.timetable is not None
    assert validate(school, res.timetable).ok
