"""Plain-English explanations: why there is no timetable, and which limits are binding.

*Infeasible:* every hard rule is placed behind its own assumption literal, CP-SAT proves the
model infeasible and returns a subset of the literals that is already contradictory (an
"unsat core"). The core is then shrunk by deletion: drop one rule at a time and re-solve;
if the rest is still contradictory the rule was not needed. What is left is a minimal
conflicting set when every re-solve finished within its time limit, and a small (but not
proven minimal) one otherwise; the result says which.

*Feasible:* resources running close to full (a teacher in 24 of their 25 free slots, a lab
booked 95% of the week) are the ones that constrain the solution, so they are listed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .issues import Issue
from .model import HOME, School, Slot, Timetable
from .prechecks import run_prechecks
from .solver import STATUS_NAMES, ModelBuilder, SolveSettings, configure


@dataclass
class CoreItem:
    group: str
    text: str
    hint: str


@dataclass
class Explanation:
    status: str  # "feasible" | "infeasible" | "unknown"
    prechecks: list[Issue] = field(default_factory=list)
    core: list[CoreItem] = field(default_factory=list)
    minimal: bool = False
    note: str = ""

    def render(self) -> str:
        lines: list[str] = []
        for i in self.prechecks:
            lines.append(str(i))
        if self.status == "infeasible":
            if self.core:
                kind = "minimal" if self.minimal else "small (not proven minimal)"
                lines.append("")
                lines.append(
                    f"No timetable exists. These {len(self.core)} conditions cannot all hold "
                    f"together ({kind} conflicting set):"
                )
                for n, item in enumerate(self.core, 1):
                    lines.append(f"  {n}. {item.text}")
                hints = sorted({c.hint for c in self.core if c.hint})
                if hints:
                    lines.append("")
                    lines.append("Ways out (change any one of the above):")
                    lines.extend(f"  - {h}" for h in hints)
            else:
                lines.append("No timetable exists, but no smaller conflicting set was found.")
        elif self.status == "feasible":
            lines.append("A timetable exists: every hard rule can be satisfied together.")
        else:
            lines.append(self.note or "The solver ran out of time before deciding.")
        return "\n".join(lines)


def describe_group(school: School, group: str) -> tuple[str, str]:
    """(plain-English statement of the rule, suggestion for relaxing it)."""
    kind, _, rest = group.partition(":")
    cal = school.calendar
    if kind == "req":
        cid, sid = rest.split(":")
        r = school.requirement(cid, sid)
        assert r is not None
        sname = school.subjects[sid].name
        dbl = f", {r.doubles} of them as double lessons" if r.doubles else ""
        return (
            f"Class {school.classes[cid].name} must get {r.lessons} {sname} lessons a week{dbl} "
            f"(taught by {r.teacher_id})",
            f"reduce {sname} lessons for {school.classes[cid].name} in requirements.csv",
        )
    if kind == "perday":
        cid, sid = rest.split(":")
        limit = school.subject_max_per_day(sid)
        return (
            f"Class {school.classes[cid].name} may have at most {limit} {school.subjects[sid].name}"
            " lessons in one day",
            "raise max_per_subject_per_day (or the subject's max_per_day)",
        )
    if kind == "class":
        return (
            f"Class {school.classes[rest].name} can only be in one lesson at a time",
            "",
        )
    if kind == "teacher-clash":
        t = school.teachers[rest]
        return (
            f"Teacher {rest} ({t.name}) can only teach one class at a time",
            f"give some of {rest}'s classes to another teacher",
        )
    if kind == "teacher-avail":
        t = school.teachers[rest]
        return (
            f"Teacher {rest} ({t.name}) is unavailable {_summarise_slots(school, t.unavailable)}",
            f"free up some of {rest}'s unavailable slots in teachers.csv",
        )
    if kind == "teacher-load":
        t = school.teachers[rest]
        return (
            f"Teacher {rest} ({t.name}) teaches at most {t.max_per_week} lessons a week and "
            f"{min(t.max_per_day, 99)} a day",
            f"raise {rest}'s limits or reassign some of their lessons",
        )
    if kind == "rooms":
        rooms = [r.name for r in school.rooms.values() if r.type == rest]
        return (
            f"Each {rest} room ({', '.join(rooms)}) hosts one class at a time and must be big "
            "enough for the class",
            f"add a {rest} room or reduce the lessons that need one",
        )
    _ = cal
    return (group, "")


def _summarise_slots(school: School, slots: frozenset[Slot]) -> str:
    cal = school.calendar
    by_day: dict[int, list[int]] = defaultdict(list)
    for d, p in sorted(slots):
        if cal.is_valid((d, p)):
            by_day[d].append(p)
    if not by_day:
        return "never"
    parts = []
    for d, ps in by_day.items():
        if len(ps) == len(cal.valid_periods(d)):
            parts.append(f"all day {cal.days[d]}")
        else:
            parts.append(f"{cal.days[d]} {', '.join(cal.periods[p].label for p in ps)}")
    return "; ".join(parts)


def explain_infeasible(
    school: School,
    *,
    time_limit: float = 30.0,
    shrink_time: float = 10.0,
    seed: int = 1,
    workers: int = 0,
) -> Explanation:
    """Decide feasibility; if infeasible, return a small conflicting set of rules."""
    pre = run_prechecks(school)
    builder = ModelBuilder(school, explain=True, soft=False)
    model = builder.model
    lits = list(builder.groups.values())
    names = {lit.Index(): name for name, lit in builder.groups.items()}
    model.AddAssumptions(lits)
    solver = cp_model.CpSolver()
    configure(solver, SolveSettings(time_limit=time_limit, seed=seed, workers=workers))
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Explanation("feasible", pre)
    if status != cp_model.INFEASIBLE:
        return Explanation(
            "unknown", pre, note=f"Solver stopped with status {STATUS_NAMES.get(status, status)}."
        )
    core = [names[i] for i in solver.SufficientAssumptionsForInfeasibility()]
    core, minimal = _shrink(builder, core, shrink_time, seed)
    items = []
    for g in core:
        text, hint = describe_group(school, g)
        items.append(CoreItem(g, text, hint))
    return Explanation("infeasible", pre, items, minimal)


def _shrink(
    builder: ModelBuilder, core: list[str], per_call: float, seed: int
) -> tuple[list[str], bool]:
    """Deletion filter: drop each rule in turn and keep it dropped if still infeasible."""
    model = builder.model
    current = list(core)
    minimal = True
    for g in list(core):
        trial = [c for c in current if c != g]
        model.ClearAssumptions()
        model.AddAssumptions([builder.groups[c] for c in trial])
        solver = cp_model.CpSolver()
        configure(solver, SolveSettings(time_limit=per_call, seed=seed, workers=1))
        status = solver.Solve(model)
        if status == cp_model.INFEASIBLE:
            # the smaller set is already contradictory; use the solver's own (maybe smaller) core
            idx = {builder.groups[c].Index(): c for c in trial}
            current = [idx[i] for i in solver.SufficientAssumptionsForInfeasibility()]
        elif status == cp_model.UNKNOWN:
            minimal = False
    return current, minimal


# ---------------------------------------------------------------------------------------
@dataclass
class Binding:
    kind: str  # "teacher" | "class" | "room-type"
    entity: str
    used: int
    available: int
    text: str

    @property
    def utilisation(self) -> float:
        return self.used / self.available if self.available else 1.0


def binding_constraints(
    school: School, timetable: Timetable, threshold: float = 0.9
) -> list[Binding]:
    """Resources close to full in a given timetable, fullest first."""
    cal = school.calendar
    n_slots = len(cal.slots)
    out: list[Binding] = []
    teacher_used: dict[str, int] = defaultdict(int)
    class_used: dict[str, int] = defaultdict(int)
    room_used: dict[str, int] = defaultdict(int)
    for e in timetable.events:
        teacher_used[e.teacher_id] += e.length
        class_used[e.class_id] += e.length
        room_used[e.room_id] += e.length
    for tid, t in school.teachers.items():
        used = teacher_used.get(tid, 0)
        free = len([s for s in cal.slots if s not in t.unavailable])
        cap = min(free, t.max_per_week)
        if used and cap and used / cap >= threshold:
            why = "available slots" if free <= t.max_per_week else "weekly maximum"
            out.append(
                Binding(
                    "teacher",
                    tid,
                    used,
                    cap,
                    f"Teacher {tid} ({t.name}) teaches {used} of {cap} possible lessons "
                    f"(limited by {why})",
                )
            )
    for cid, klass in school.classes.items():
        used = class_used.get(cid, 0)
        if used and used / n_slots >= threshold:
            out.append(
                Binding(
                    "class",
                    cid,
                    used,
                    n_slots,
                    f"Class {klass.name} is in lessons for {used} of {n_slots} slots",
                )
            )
    types: dict[str, list[str]] = defaultdict(list)
    for r in school.rooms.values():
        if r.type != HOME and any(s.room_type == r.type for s in school.subjects.values()):
            types[r.type].append(r.id)
    for rtype, ids in types.items():
        used = sum(room_used.get(i, 0) for i in ids)
        cap = len(ids) * n_slots
        if used and used / cap >= min(threshold, 0.6):
            out.append(
                Binding(
                    "room-type",
                    rtype,
                    used,
                    cap,
                    f"'{rtype}' rooms are booked for {used} of {cap} room-periods "
                    f"({len(ids)} room(s))",
                )
            )
    out.sort(key=lambda b: -b.utilisation)
    return out
