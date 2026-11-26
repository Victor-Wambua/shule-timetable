"""CP-SAT model for the timetable, and the solve entry point.

Modelling in one paragraph. For every requirement (class, subject, teacher, n lessons,
d doubles) and every slot there are two kinds of 0/1 "event start" variables: ``b1`` (a
single-period lesson starts here) and ``b2`` (a two-period double starts here, only offered
where the next period is in the same break-free segment). A derived ``x`` says "this
requirement occupies this slot" and equals ``b1[s] + b2[s] + b2[s-1]``. Every clash rule is
then a sum of ``x`` over a set of requirements being at most one. Rooms are assigned with a
third layer of variables, one per (event start, eligible room), only for lessons that need
a specialist room.

The same builder serves three jobs: plain solving, ``explain`` (hard constraints grouped
behind assumption literals so CP-SAT can return an unsat core) and ``repair`` (an extra
"keep the old timetable" objective).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

from .model import Event, Requirement, School, Slot, Timetable
from .scoring import ScoreBreakdown, min_days_needed, score

STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


@dataclass
class SolveSettings:
    time_limit: float = 30.0
    seed: int = 1
    workers: int = 0  # 0 lets OR-Tools choose; tests pass 1 for determinism
    soft: bool = True  # False = just find any timetable that satisfies the hard rules
    hint: Timetable | None = None
    relative_gap: float = 0.0
    log: bool = False


@dataclass
class SolveResult:
    status: str
    timetable: Timetable | None
    objective: float | None = None
    best_bound: float | None = None
    wall_time: float = 0.0
    breakdown: ScoreBreakdown | None = None
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def gap(self) -> float | None:
        """Relative gap between the best solution and the proven lower bound."""
        if self.objective is None or self.best_bound is None:
            return None
        if self.objective == 0:
            return 0.0 if self.best_bound <= 0 else 1.0
        return max(0.0, (self.objective - self.best_bound) / abs(self.objective))

    @property
    def solved(self) -> bool:
        return self.timetable is not None


GROUP_KINDS = ("req", "perday", "class", "teacher-clash", "teacher-avail", "teacher-load", "rooms")


class ModelBuilder:
    def __init__(self, school: School, *, explain: bool = False, soft: bool = True) -> None:
        self.school = school
        self.explain = explain
        self.model = cp_model.CpModel()
        self.groups: dict[str, cp_model.IntVar] = {}
        self.reqs = list(school.requirements)
        self.slots: tuple[Slot, ...] = school.calendar.slots
        self.b1: dict[tuple[int, Slot], cp_model.IntVar] = {}
        self.b2: dict[tuple[int, Slot], cp_model.IntVar] = {}
        self.x: dict[tuple[int, Slot], cp_model.IntVar] = {}
        self.e1: dict[tuple[int, Slot, str], cp_model.IntVar] = {}
        self.e2: dict[tuple[int, Slot, str], cp_model.IntVar] = {}
        self.soft_terms: list[tuple[int, Any]] = []
        self._build_events()
        self._build_hard()
        if soft and not explain:
            self._build_soft()

    # ------------------------------------------------------------------ helpers
    def _group(self, name: str) -> cp_model.IntVar | None:
        if not self.explain:
            return None
        if name not in self.groups:
            self.groups[name] = self.model.new_bool_var(f"g[{name}]")
        return self.groups[name]

    def _add(self, constraint: Any, group: str) -> None:
        lit = self._group(group)
        if lit is not None:
            constraint.only_enforce_if(lit)

    def _x_at(self, ri: int, slot: Slot) -> cp_model.IntVar | None:
        return self.x.get((ri, slot))

    # ------------------------------------------------------------------ variables
    def _build_events(self) -> None:
        cal = self.school.calendar
        m = self.model
        double_starts = {(d, p) for d in range(len(cal.days)) for p in cal.double_starts(d)}
        for ri, r in enumerate(self.reqs):
            singles = r.lessons - 2 * r.doubles
            for s in self.slots:
                if singles > 0:
                    self.b1[(ri, s)] = m.new_bool_var(f"b1[{ri},{s}]")
                if r.doubles > 0 and s in double_starts:
                    self.b2[(ri, s)] = m.new_bool_var(f"b2[{ri},{s}]")
            for s in self.slots:
                parts = []
                if (ri, s) in self.b1:
                    parts.append(self.b1[(ri, s)])
                if (ri, s) in self.b2:
                    parts.append(self.b2[(ri, s)])
                prev = (s[0], s[1] - 1)
                if (ri, prev) in self.b2:
                    parts.append(self.b2[(ri, prev)])
                xv = m.new_bool_var(f"x[{ri},{s}]")
                if parts:
                    m.add(xv == sum(parts))
                else:
                    m.add(xv == 0)
                self.x[(ri, s)] = xv
        # specialist-room assignment variables
        for ri, r in enumerate(self.reqs):
            pool = self.school.pool_rooms_for(r)
            for s in self.slots:
                if (ri, s) in self.b1 and self.school.uses_pool(r, is_double=False):
                    for room in pool:
                        self.e1[(ri, s, room.id)] = m.new_bool_var(f"e1[{ri},{s},{room.id}]")
                if (ri, s) in self.b2 and self.school.uses_pool(r, is_double=True):
                    for room in pool:
                        self.e2[(ri, s, room.id)] = m.new_bool_var(f"e2[{ri},{s},{room.id}]")

    # ------------------------------------------------------------------ hard rules
    def _build_hard(self) -> None:
        school = self.school
        cal = school.calendar
        m = self.model

        by_class: dict[str, list[int]] = defaultdict(list)
        by_teacher: dict[str, list[int]] = defaultdict(list)
        for ri, r in enumerate(self.reqs):
            by_class[r.class_id].append(ri)
            by_teacher[r.teacher_id].append(ri)

        # required lesson counts, doubles, and per-day limit
        for ri, r in enumerate(self.reqs):
            gname = f"req:{r.class_id}:{r.subject_id}"
            singles = r.lessons - 2 * r.doubles
            self._add(
                m.add(sum(self.b1[(ri, s)] for s in self.slots if (ri, s) in self.b1) == singles),
                gname,
            )
            self._add(
                m.add(sum(self.b2[(ri, s)] for s in self.slots if (ri, s) in self.b2) == r.doubles),
                gname,
            )
            limit = school.subject_max_per_day(r.subject_id)
            for d in range(len(cal.days)):
                terms = [self.x[(ri, (d, p))] for p in cal.valid_periods(d)]
                if len(terms) > limit:
                    self._add(m.add(sum(terms) <= limit), f"perday:{r.class_id}:{r.subject_id}")

        # a class is in one place at a time
        for cid, ris in by_class.items():
            for s in self.slots:
                self._add(m.add(sum(self.x[(ri, s)] for ri in ris) <= 1), f"class:{cid}")

        # teachers
        for tid, ris in by_teacher.items():
            t = school.teachers[tid]
            for s in self.slots:
                self._add(m.add(sum(self.x[(ri, s)] for ri in ris) <= 1), f"teacher-clash:{tid}")
                if s in t.unavailable:
                    for ri in ris:
                        self._add(m.add(self.x[(ri, s)] == 0), f"teacher-avail:{tid}")
            self._add(
                m.add(sum(self.x[(ri, s)] for ri in ris for s in self.slots) <= t.max_per_week),
                f"teacher-load:{tid}",
            )
            for d in range(len(cal.days)):
                terms = [self.x[(ri, (d, p))] for ri in ris for p in cal.valid_periods(d)]
                if len(terms) > t.max_per_day:
                    self._add(m.add(sum(terms) <= t.max_per_day), f"teacher-load:{tid}")

        # rooms: every specialist event gets exactly one eligible room; no room is shared
        e1_by: dict[tuple[int, Slot], list[cp_model.IntVar]] = defaultdict(list)
        e2_by: dict[tuple[int, Slot], list[cp_model.IntVar]] = defaultdict(list)
        use: dict[tuple[str, Slot], list[cp_model.IntVar]] = defaultdict(list)
        for (ri, s, k), v in self.e1.items():
            e1_by[(ri, s)].append(v)
            use[(k, s)].append(v)
        for (ri, s, k), v in self.e2.items():
            e2_by[(ri, s)].append(v)
            use[(k, s)].append(v)
            nxt = (s[0], s[1] + 1)
            use[(k, nxt)].append(v)
        for (ri, s), vs in e1_by.items():
            gname = f"rooms:{school.subjects[self.reqs[ri].subject_id].room_type}"
            self._add(m.add(sum(vs) == self.b1[(ri, s)]), gname)
        for (ri, s), vs in e2_by.items():
            gname = f"rooms:{school.subjects[self.reqs[ri].subject_id].room_type}"
            self._add(m.add(sum(vs) == self.b2[(ri, s)]), gname)
        room_type = {k: room.type for k, room in school.rooms.items()}
        for (k, _s), vs in use.items():
            if len(vs) > 1:
                self._add(m.add(sum(vs) <= 1), f"rooms:{room_type[k]}")

    # ------------------------------------------------------------------ soft rules
    def _build_soft(self) -> None:
        school = self.school
        cal = school.calendar
        w = school.weights
        m = self.model
        n_days = len(cal.days)
        active_days = [d for d in range(n_days) if cal.valid_periods(d)]

        by_class: dict[str, list[int]] = defaultdict(list)
        by_teacher: dict[str, list[int]] = defaultdict(list)
        for ri, r in enumerate(self.reqs):
            by_class[r.class_id].append(ri)
            by_teacher[r.teacher_id].append(ri)

        def busy_vars(ris: list[int], name: str) -> dict[Slot, cp_model.IntVar]:
            out: dict[Slot, cp_model.IntVar] = {}
            for s in self.slots:
                v = m.new_bool_var(f"{name}@{s}")
                m.add(v == sum(self.x[(ri, s)] for ri in ris))
                out[s] = v
            return out

        need_t = w.teacher_consecutive or w.teacher_gaps or w.teacher_days_compact
        need_c = w.class_gaps or w.balance_daily_load or w.light_slots
        t_busy = (
            {tid: busy_vars(ris, f"tb[{tid}]") for tid, ris in by_teacher.items()} if need_t else {}
        )
        c_busy = (
            {cid: busy_vars(ris, f"cb[{cid}]") for cid, ris in by_class.items()} if need_c else {}
        )

        # spread subjects across the week
        if w.spread_subjects:
            for ri, r in enumerate(self.reqs):
                target = min(r.blocks, len(active_days))
                used = []
                for d in active_days:
                    u = m.new_bool_var(f"u[{ri},{d}]")
                    m.add_max_equality(u, [self.x[(ri, (d, p))] for p in cal.valid_periods(d)])
                    used.append(u)
                missing = m.new_int_var(0, target, f"missing[{ri}]")
                m.add(missing == target - sum(used))
                self.soft_terms.append((w.spread_subjects, missing))

        # teachers: long back-to-back runs, gaps, working days
        k = school.limits.max_consecutive_lessons
        worked_days: dict[str, list[cp_model.IntVar]] = {}
        for tid, busy in t_busy.items():
            for d in active_days:
                if w.teacher_consecutive:
                    for stretch in cal.stretches(d):
                        for i in range(len(stretch) - k):
                            window = [busy[(d, p)] for p in stretch[i : i + k + 1]]
                            v = m.new_bool_var(f"run[{tid},{d},{i}]")
                            m.add_bool_and(window).only_enforce_if(v)
                            m.add_bool_or([b.negated() for b in window] + [v])
                            self.soft_terms.append((w.teacher_consecutive, v))
                if w.teacher_gaps:
                    for g in self._gap_vars(
                        [busy[(d, p)] for p in cal.valid_periods(d)], f"tg[{tid},{d}]"
                    ):
                        self.soft_terms.append((w.teacher_gaps, g))
                if w.teacher_days_compact:
                    worked = m.new_bool_var(f"worked[{tid},{d}]")
                    m.add_max_equality(worked, [busy[(d, p)] for p in cal.valid_periods(d)])
                    worked_days.setdefault(tid, []).append(worked)
            if w.teacher_days_compact:
                floor = min_days_needed(school, tid)
                excess = m.new_int_var(0, len(active_days), f"excess_days[{tid}]")
                m.add_max_equality(excess, [sum(worked_days[tid]) - floor, 0])
                self.soft_terms.append((w.teacher_days_compact, excess))

        # classes: gaps, balanced days
        for cid, busy in c_busy.items():
            if w.class_gaps:
                for d in active_days:
                    for g in self._gap_vars(
                        [busy[(d, p)] for p in cal.valid_periods(d)], f"cg[{cid},{d}]"
                    ):
                        self.soft_terms.append((w.class_gaps, g))
            if w.balance_daily_load:
                total = sum(self.reqs[ri].lessons for ri in by_class[cid])
                target = -(-total // len(active_days)) if active_days else 0
                for d in active_days:
                    load = sum(busy[(d, p)] for p in cal.valid_periods(d))
                    over = m.new_int_var(0, len(cal.valid_periods(d)), f"over[{cid},{d}]")
                    m.add_max_equality(over, [load - target, 0])
                    self.soft_terms.append((w.balance_daily_load, over))
            if w.light_slots:
                for s in school.light_slots:
                    self.soft_terms.append((w.light_slots, busy[s]))

        # per-lesson preferences
        morning = school.morning_until()
        for ri, r in enumerate(self.reqs):
            subject = school.subjects[r.subject_id]
            for s in self.slots:
                d, p = s
                valid = cal.valid_periods(d)
                if w.heavy_morning and subject.heavy and p > morning:
                    self.soft_terms.append((w.heavy_morning, self.x[(ri, s)]))
                if w.avoid_edges and subject.avoid_edges and (p == valid[0] or p == valid[-1]):
                    self.soft_terms.append((w.avoid_edges, self.x[(ri, s)]))

        self.model.minimize(sum(wt * v for wt, v in self.soft_terms) if self.soft_terms else 0)

    def _gap_vars(self, busy: list[cp_model.IntVar], name: str) -> list[cp_model.IntVar]:
        """Exact 0/1 variables, one per idle period lying between two busy periods."""
        n = len(busy)
        if n < 3:
            return []
        m = self.model
        before: list[Any] = [None] * n
        after: list[Any] = [None] * n
        before[1] = busy[0]
        for i in range(2, n):
            v = m.new_bool_var(f"{name}.before{i}")
            m.add_max_equality(v, [busy[i - 1], before[i - 1]])
            before[i] = v
        after[n - 2] = busy[n - 1]
        for i in range(n - 3, -1, -1):
            v = m.new_bool_var(f"{name}.after{i}")
            m.add_max_equality(v, [busy[i + 1], after[i + 1]])
            after[i] = v
        gaps = []
        for i in range(1, n - 1):
            g = m.new_bool_var(f"{name}.gap{i}")
            m.add_bool_and([before[i], after[i], busy[i].negated()]).only_enforce_if(g)
            m.add_bool_or([before[i].negated(), after[i].negated(), busy[i], g])
            gaps.append(g)
        return gaps

    # ------------------------------------------------------------------ hints & output
    def add_hint(self, timetable: Timetable) -> None:
        wanted_b1: set[tuple[int, Slot]] = set()
        wanted_b2: set[tuple[int, Slot]] = set()
        wanted_room: set[tuple[int, Slot, str]] = set()
        index = {r.key: i for i, r in enumerate(self.reqs)}
        for e in timetable.events:
            ri = index.get((e.class_id, e.subject_id))
            if ri is None:
                continue
            s = (e.day, e.period)
            if e.length == 1:
                wanted_b1.add((ri, s))
                wanted_room.add((ri, s, e.room_id))
            else:
                wanted_b2.add((ri, s))
                wanted_room.add((ri, s, e.room_id))
        for k1, v in self.b1.items():
            self.model.add_hint(v, int(k1 in wanted_b1))
        for k2, v in self.b2.items():
            self.model.add_hint(v, int(k2 in wanted_b2))
        for k3, v in self.e1.items():
            self.model.add_hint(v, int(k3 in wanted_room and (k3[0], k3[1]) in wanted_b1))
        for k4, v in self.e2.items():
            self.model.add_hint(v, int(k4 in wanted_room and (k4[0], k4[1]) in wanted_b2))

    def extract(self, solver: cp_model.CpSolver) -> Timetable:
        chosen: dict[tuple[int, Slot, int], str] = {}
        for (ri, s1, k1), v1 in self.e1.items():
            if solver.boolean_value(v1):
                chosen[(ri, s1, 1)] = k1
        for (ri, s2, k2), v2 in self.e2.items():
            if solver.boolean_value(v2):
                chosen[(ri, s2, 2)] = k2
        events: list[Event] = []
        for table, length in ((self.b1, 1), (self.b2, 2)):
            for (ri, s), v in table.items():
                if solver.boolean_value(v):
                    r: Requirement = self.reqs[ri]
                    room = chosen.get((ri, s, length), self.school.classes[r.class_id].home_room)
                    events.append(
                        Event(r.class_id, r.subject_id, r.teacher_id, room, s[0], s[1], length)
                    )
        events.sort(key=lambda e: (e.day, e.period, e.class_id))
        return Timetable(tuple(events))


def configure(solver: cp_model.CpSolver, settings: SolveSettings) -> None:
    solver.parameters.max_time_in_seconds = settings.time_limit
    solver.parameters.random_seed = settings.seed
    solver.parameters.num_workers = settings.workers
    solver.parameters.relative_gap_limit = settings.relative_gap
    solver.parameters.log_search_progress = settings.log


def solve(school: School, settings: SolveSettings | None = None) -> SolveResult:
    settings = settings or SolveSettings()
    started = time.perf_counter()
    builder = ModelBuilder(school, soft=settings.soft)
    if settings.hint is not None:
        builder.add_hint(settings.hint)
    solver = cp_model.CpSolver()
    configure(solver, settings)
    status = solver.solve(builder.model)
    wall = time.perf_counter() - started
    name = STATUS_NAMES.get(status, str(status))
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(name, None, wall_time=wall)
    timetable = builder.extract(solver)
    objective = solver.objective_value if builder.soft_terms else 0.0
    bound = solver.best_objective_bound if builder.soft_terms else 0.0
    result = SolveResult(
        name,
        timetable,
        objective=objective,
        best_bound=bound,
        wall_time=wall,
        breakdown=score(school, timetable),
        stats={
            "solver_wall_time": solver.wall_time,
            "branches": solver.num_branches,
            "conflicts": solver.num_conflicts,
            "variables": len(builder.model.proto.variables),
            "constraints": len(builder.model.proto.constraints),
            "workers": settings.workers,
            "seed": settings.seed,
            "time_limit": settings.time_limit,
        },
    )
    return result
