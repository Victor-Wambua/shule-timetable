from __future__ import annotations

import pytest

from shule_timetable.model import SpecError

from .helpers import calendar


def test_slots_count_and_blocked() -> None:
    cal = calendar()
    assert len(cal.slots) == 18
    assert (0, 5) in cal.slots


def test_segments_are_cut_by_every_break_but_stretches_only_by_long_breaks() -> None:
    cal = calendar()
    assert cal.segments(0) == [[0, 1], [2, 3], [4, 5]]
    assert cal.stretches(0) == [[0, 1, 2, 3], [4, 5]]


def test_double_starts_never_cross_a_break() -> None:
    assert calendar().double_starts(0) == [0, 2, 4]


def test_short_day_and_blocked_slot() -> None:
    from dataclasses import replace

    cal = replace(calendar(), day_lengths=(6, 6, 3), blocked=frozenset({(0, 0)}))
    assert cal.valid_periods(2) == [0, 1, 2]
    assert cal.valid_periods(0) == [1, 2, 3, 4, 5]
    assert cal.segments(2) == [[0, 1], [2]]
    assert not cal.is_valid((0, 0)) and not cal.is_valid((2, 3))


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("Mon:P1", {(0, 0)}),
        ("Mon:P1-P3", {(0, 0), (0, 1), (0, 2)}),
        ("Tue:*", {(1, p) for p in range(6)}),
        ("Mon-Tue:P6", {(0, 5), (1, 5)}),
        ("Wed:P1,P3", {(2, 0), (2, 2)}),
        ("Mon:P1; Tue:P2", {(0, 0), (1, 1)}),
        ("mon:p1", {(0, 0)}),
    ],
)
def test_parse_slots(spec: str, expected: set[tuple[int, int]]) -> None:
    assert calendar().parse_slots(spec) == expected


@pytest.mark.parametrize("spec", ["Funday:P1", "Mon:P99", "Mon", "Mon:P3-P1", "Wed-Mon:P1"])
def test_parse_slots_errors(spec: str) -> None:
    with pytest.raises(SpecError):
        calendar().parse_slots(spec)
