"""Soft-constraint score, computed in plain Python from a finished timetable.

The solver minimises the same quantity inside CP-SAT. Computing it again here, from the
output alone, gives (a) the breakdown shown to users and (b) a cross-check: for any
instance solved to optimality the two must agree, and a test asserts that they do.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .model import School, Slot, Timetable

LABELS = {
    "spread_subjects": "Subjects spread across the week",
    "teacher_consecutive": "No long back-to-back runs for teachers",
    "teacher_gaps": "Few idle gaps in a teacher's day",
    "class_gaps": "No free periods in the middle of a class's day",
    "heavy_morning": "Heavy subjects in the morning",
    "balance_daily_load": "Even daily load for each class",
    "avoid_edges": "Flagged subjects avoid first/last period",
    "teacher_days_compact": "Teachers get free days where their load allows",
    "light_slots": "Keep marked slots light",
}


@dataclass
class ScoreItem:
    name: str
    label: str
    count: int  # how many times the undesirable thing happens
    weight: int
    detail: dict[str, int] = field(default_factory=dict)  # entity id -> count

    @property
    def penalty(self) -> int:
        return self.count * self.weight


@dataclass
class ScoreBreakdown:
    items: list[ScoreItem]

    @property
    def total(self) -> int:
        return sum(i.penalty for i in self.items)

    def as_dict(self) -> dict[str, int]:
        return {i.name: i.penalty for i in self.items}


def min_days_needed(school: School, teacher_id: str) -> int:
    """Fewest days a teacher's weekly load could be squeezed into (daily cap permitting)."""
    t = school.teachers[teacher_id]
    load = sum(r.lessons for r in school.teacher_requirements(teacher_id))
    longest = max(
        (len(school.calendar.valid_periods(d)) for d in range(len(school.calendar.days))), default=1
    )
    cap = max(1, min(t.max_per_day, longest))
    return -(-load // cap)


def _busy_by_day(
    events_by_entity: dict[str, set[Slot]], n_days: int
) -> dict[tuple[str, int], set[int]]:
    out: dict[tuple[str, int], set[int]] = defaultdict(set)
    for ent, slots in events_by_entity.items():
        for d, p in slots:
            out[(ent, d)].add(p)
    return out


def _gaps(school: School, busy: dict[tuple[str, int], set[int]]) -> dict[str, int]:
    cal = school.calendar
    out: dict[str, int] = defaultdict(int)
    for (ent, d), periods in busy.items():
        valid = cal.valid_periods(d)
        idx = [i for i, p in enumerate(valid) if p in periods]
        if len(idx) >= 2:
            out[ent] += (idx[-1] - idx[0] + 1) - len(idx)
    return {k: v for k, v in out.items() if v}


def score(school: School, timetable: Timetable) -> ScoreBreakdown:
    cal = school.calendar
    w = school.weights
    n_days = len(cal.days)
    active_days = [d for d in range(n_days) if cal.valid_periods(d)]

    teacher_slots: dict[str, set[Slot]] = defaultdict(set)
    class_slots: dict[str, set[Slot]] = defaultdict(set)
    for e in timetable.events:
        teacher_slots[e.teacher_id].update(e.slots)
        class_slots[e.class_id].update(e.slots)
    t_busy = _busy_by_day(teacher_slots, n_days)
    c_busy = _busy_by_day(class_slots, n_days)

    # spread
    spread: dict[str, int] = {}
    days_used: dict[tuple[str, str], set[int]] = defaultdict(set)
    for e in timetable.events:
        days_used[(e.class_id, e.subject_id)].add(e.day)
    for r in school.requirements:
        target = min(r.blocks, len(active_days))
        missing = max(0, target - len(days_used.get(r.key, set())))
        if missing:
            spread[f"{r.class_id}/{r.subject_id}"] = missing

    # consecutive
    k = school.limits.max_consecutive_lessons
    consecutive: dict[str, int] = defaultdict(int)
    for (tid, d), periods in t_busy.items():
        for stretch in cal.stretches(d):
            for i in range(len(stretch) - k):
                if all(p in periods for p in stretch[i : i + k + 1]):
                    consecutive[tid] += 1

    # heavy morning, edges, light slots
    morning = school.morning_until()
    heavy: dict[str, int] = defaultdict(int)
    edges: dict[str, int] = defaultdict(int)
    light: dict[str, int] = defaultdict(int)
    for e in timetable.events:
        subj = school.subjects[e.subject_id]
        for d, p in e.slots:
            valid = cal.valid_periods(d)
            if subj.heavy and p > morning:
                heavy[e.class_id] += 1
            if subj.avoid_edges and (p == valid[0] or p == valid[-1]):
                edges[e.class_id] += 1
            if (d, p) in school.light_slots:
                light[e.class_id] += 1

    # balance
    balance: dict[str, int] = defaultdict(int)
    for cid, slots in class_slots.items():
        total = len(slots)
        target = -(-total // len(active_days)) if active_days else 0
        for d in active_days:
            over = len(c_busy.get((cid, d), set())) - target
            if over > 0:
                balance[cid] += over

    # compact days: working days beyond the fewest the teacher's load could fit into
    days_worked: dict[str, int] = defaultdict(int)
    for (tid, _d), periods in t_busy.items():
        if periods:
            days_worked[tid] += 1
    days_worked = {tid: max(0, n - min_days_needed(school, tid)) for tid, n in days_worked.items()}

    def item(name: str, detail: dict[str, int]) -> ScoreItem:
        d = {k: v for k, v in detail.items() if v}
        return ScoreItem(name, LABELS[name], sum(d.values()), getattr(w, name), dict(d))

    return ScoreBreakdown(
        [
            item("spread_subjects", spread),
            item("teacher_consecutive", dict(consecutive)),
            item("teacher_gaps", _gaps(school, t_busy)),
            item("class_gaps", _gaps(school, c_busy)),
            item("heavy_morning", dict(heavy)),
            item("balance_daily_load", dict(balance)),
            item("avoid_edges", dict(edges)),
            item("teacher_days_compact", dict(days_worked)),
            item("light_slots", dict(light)),
        ]
    )
