"""Plain data model shared by the loader, solver, validator and renderers.

Nothing in this module imports OR-Tools, so the independent validator can depend on it
without depending on the solver.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field, replace
from functools import cached_property

Slot = tuple[int, int]  # (day index, period index)

HOME = "home"  # room_type meaning "the class's own classroom"


class SpecError(ValueError):
    """A slot specification such as ``Mon:P1-P3`` could not be understood."""


@dataclass(frozen=True)
class Period:
    label: str
    start: str  # "HH:MM"
    end: str


@dataclass(frozen=True)
class Break:
    after: int  # index of the period the break follows
    name: str
    long: bool = False  # a long break (lunch) ends a "stretch" of back-to-back teaching


@dataclass(frozen=True)
class Calendar:
    days: tuple[str, ...]
    periods: tuple[Period, ...]
    breaks: tuple[Break, ...] = ()
    day_lengths: tuple[int, ...] = ()  # periods that exist on each day (short days)
    blocked: frozenset[Slot] = frozenset()  # slots where no lessons run (assembly, clubs)

    def __post_init__(self) -> None:
        if not self.day_lengths:
            object.__setattr__(self, "day_lengths", tuple(len(self.periods) for _ in self.days))

    def is_valid(self, slot: Slot) -> bool:
        d, p = slot
        return 0 <= d < len(self.days) and 0 <= p < self.day_lengths[d] and slot not in self.blocked

    def valid_periods(self, day: int) -> list[int]:
        return [p for p in range(self.day_lengths[day]) if (day, p) not in self.blocked]

    @cached_property
    def slots(self) -> tuple[Slot, ...]:
        return tuple((d, p) for d in range(len(self.days)) for p in self.valid_periods(d))

    @cached_property
    def _break_after(self) -> dict[int, Break]:
        return {b.after: b for b in self.breaks}

    def break_between(self, p: int, q: int) -> bool:
        """True if any break lies between consecutive periods p and q (q > p)."""
        return any(p <= b.after < q for b in self.breaks)

    def long_break_between(self, p: int, q: int) -> bool:
        return any(p <= b.after < q and b.long for b in self.breaks)

    def _runs(self, day: int, cut_on_long_only: bool) -> list[list[int]]:
        runs: list[list[int]] = []
        for p in self.valid_periods(day):
            if runs and runs[-1][-1] == p - 1:
                cut = (
                    self.long_break_between(p - 1, p)
                    if cut_on_long_only
                    else self.break_between(p - 1, p)
                )
                if not cut:
                    runs[-1].append(p)
                    continue
            runs.append([p])
        return runs

    def segments(self, day: int) -> list[list[int]]:
        """Runs of consecutive periods with no break at all between them.

        A double lesson must fit inside one segment: it cannot straddle tea, a short break
        or lunch.
        """
        return self._runs(day, cut_on_long_only=False)

    def stretches(self, day: int) -> list[list[int]]:
        """Runs of consecutive periods not interrupted by a *long* break.

        "Too many lessons back to back" is measured within a stretch.
        """
        return self._runs(day, cut_on_long_only=True)

    def double_starts(self, day: int) -> list[int]:
        """Periods at which a two-period lesson can begin on this day."""
        return [p for seg in self.segments(day) for p in seg[:-1]]

    def label(self, slot: Slot) -> str:
        d, p = slot
        return f"{self.days[d]} {self.periods[p].label}"

    def period_index(self, label: str) -> int:
        for i, per in enumerate(self.periods):
            if per.label.lower() == label.lower():
                return i
        raise SpecError(
            f"unknown period '{label}' (known: {', '.join(p.label for p in self.periods)})"
        )

    def day_index(self, name: str) -> int:
        for i, day in enumerate(self.days):
            if day.lower() == name.lower():
                return i
        raise SpecError(f"unknown day '{name}' (known: {', '.join(self.days)})")

    def parse_slots(self, spec: str) -> set[Slot]:
        """Parse ``"Mon:P1-P3;Fri:*;Tue-Thu:P7,P8"`` into a set of (day, period) pairs."""
        out: set[Slot] = set()
        for part in re.split(r"[;\n]", spec):
            part = part.strip()
            if not part:
                continue
            if ":" not in part:
                raise SpecError(f"'{part}' needs a day and periods, e.g. 'Mon:P1-P3' or 'Fri:*'")
            day_part, per_part = (s.strip() for s in part.split(":", 1))
            out.update(
                (d, p) for d in self._parse_days(day_part) for p in self._parse_periods(per_part)
            )
        return out

    def _parse_days(self, text: str) -> list[int]:
        if text == "*":
            return list(range(len(self.days)))
        if "-" in text:
            a, b = (self.day_index(s.strip()) for s in text.split("-", 1))
            if a > b:
                raise SpecError(f"day range '{text}' runs backwards")
            return list(range(a, b + 1))
        return [self.day_index(text)]

    def _parse_periods(self, text: str) -> list[int]:
        if text == "*":
            return list(range(len(self.periods)))
        out: list[int] = []
        for chunk in text.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                a, b = (self.period_index(s.strip()) for s in chunk.split("-", 1))
                if a > b:
                    raise SpecError(f"period range '{chunk}' runs backwards")
                out.extend(range(a, b + 1))
            else:
                out.append(self.period_index(chunk))
        return out


@dataclass(frozen=True)
class Subject:
    id: str
    name: str
    room_type: str = HOME
    room_use: str = "all"  # "all" lessons use room_type, or only the "doubles" (practicals)
    doubles: int = 0  # default number of double lessons per week for each class
    heavy: bool = False  # prefer the morning
    avoid_edges: bool = False  # avoid the first and last period of the day
    max_per_day: int | None = None  # per class; falls back to Limits.max_per_subject_per_day


@dataclass(frozen=True)
class Teacher:
    id: str
    name: str
    subjects: tuple[str, ...]
    max_per_week: int
    max_per_day: int
    unavailable: frozenset[Slot] = frozenset()


@dataclass(frozen=True)
class Room:
    id: str
    name: str
    type: str
    capacity: int


@dataclass(frozen=True)
class SchoolClass:
    id: str
    name: str
    size: int
    home_room: str


@dataclass(frozen=True)
class Requirement:
    """A class needs ``lessons`` periods of a subject per week from one named teacher."""

    class_id: str
    subject_id: str
    teacher_id: str
    lessons: int
    doubles: int = 0  # how many of those lessons are paired into two-period blocks

    @property
    def key(self) -> tuple[str, str]:
        return (self.class_id, self.subject_id)

    @property
    def blocks(self) -> int:
        """Number of separately placed events (a double counts once)."""
        return self.lessons - self.doubles


@dataclass(frozen=True)
class Weights:
    """Penalty per unit for each soft constraint. 0 switches a constraint off."""

    spread_subjects: int = 4  # per class-subject day missing from an even spread
    teacher_consecutive: int = 6  # per window of too many back-to-back lessons
    teacher_gaps: int = 2  # per idle period between a teacher's first and last lesson
    class_gaps: int = 8  # per free period in the middle of a class's day
    heavy_morning: int = 3  # per heavy-subject lesson after the morning cut-off
    balance_daily_load: int = 2  # per lesson above an even daily share (per class)
    avoid_edges: int = 3  # per lesson in the first/last period for flagged subjects
    teacher_days_compact: int = 1  # per working day beyond the fewest the load fits in
    light_slots: int = 2  # per lesson placed in a slot marked "keep light"

    def as_dict(self) -> dict[str, int]:
        return {f: getattr(self, f) for f in self.__dataclass_fields__}


@dataclass(frozen=True)
class Limits:
    max_per_subject_per_day: int = 2
    max_consecutive_lessons: int = 3
    morning_until: int | None = None  # last period index counted as "morning"


@dataclass(frozen=True)
class Term:
    start: dt.date
    weeks: int


@dataclass(frozen=True)
class School:
    name: str
    calendar: Calendar
    subjects: dict[str, Subject]
    teachers: dict[str, Teacher]
    rooms: dict[str, Room]
    classes: dict[str, SchoolClass]
    requirements: tuple[Requirement, ...]
    weights: Weights = field(default_factory=Weights)
    limits: Limits = field(default_factory=Limits)
    light_slots: frozenset[Slot] = frozenset()
    term: Term | None = None
    synthetic: bool = False

    # ---- derived helpers -------------------------------------------------
    def requirement(self, class_id: str, subject_id: str) -> Requirement | None:
        return self._req_index.get((class_id, subject_id))

    @cached_property
    def _req_index(self) -> dict[tuple[str, str], Requirement]:
        return {r.key: r for r in self.requirements}

    def subject_max_per_day(self, subject_id: str) -> int:
        s = self.subjects[subject_id]
        return s.max_per_day if s.max_per_day is not None else self.limits.max_per_subject_per_day

    def morning_until(self) -> int:
        """Last period index that counts as morning."""
        if self.limits.morning_until is not None:
            return self.limits.morning_until
        cal = self.calendar
        long_breaks = [b.after for b in cal.breaks if b.long]
        if long_breaks:
            return min(long_breaks)
        return (len(cal.periods) - 1) // 2

    def pool_rooms_for(self, req: Requirement) -> list[Room]:
        """Rooms a class could use for this requirement's specialist lessons."""
        subject = self.subjects[req.subject_id]
        size = self.classes[req.class_id].size
        return [
            r for r in self.rooms.values() if r.type == subject.room_type and r.capacity >= size
        ]

    def uses_pool(self, req: Requirement, is_double: bool) -> bool:
        subject = self.subjects[req.subject_id]
        if subject.room_type == HOME:
            return False
        return subject.room_use == "all" or is_double

    def teacher_requirements(self, teacher_id: str) -> list[Requirement]:
        return [r for r in self.requirements if r.teacher_id == teacher_id]

    def with_requirements(self, requirements: tuple[Requirement, ...]) -> School:
        return replace(self, requirements=requirements)


@dataclass(frozen=True)
class Event:
    """One lesson event: a single period, or a two-period double starting at ``period``."""

    class_id: str
    subject_id: str
    teacher_id: str
    room_id: str
    day: int
    period: int
    length: int = 1

    @property
    def slots(self) -> tuple[Slot, ...]:
        return tuple((self.day, self.period + i) for i in range(self.length))


@dataclass(frozen=True)
class Timetable:
    events: tuple[Event, ...]
    meta: dict[str, object] = field(default_factory=dict)

    def lesson_count(self) -> int:
        return sum(e.length for e in self.events)

    def by_class(self, class_id: str) -> list[Event]:
        return sorted((e for e in self.events if e.class_id == class_id), key=_order)

    def by_teacher(self, teacher_id: str) -> list[Event]:
        return sorted((e for e in self.events if e.teacher_id == teacher_id), key=_order)

    def by_room(self, room_id: str) -> list[Event]:
        return sorted((e for e in self.events if e.room_id == room_id), key=_order)


def _order(e: Event) -> tuple[int, int]:
    return (e.day, e.period)
