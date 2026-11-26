"""Repair mode: change a solved timetable as little as possible.

Given a finished timetable and a change (a teacher leaves, a teacher becomes unavailable,
a class gets an extra lesson), re-solve with two stages:

1. minimise the number of lessons that move away from where they were;
2. holding that minimum, minimise the usual soft-constraint penalty (plus a small cost for
   switching rooms on lessons that stayed put).

The answer to "the teacher left, how much changes?" is then a proven minimum, not a hope.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml
from ortools.sat.python import cp_model

from .issues import InputError, Issue
from .model import Event, Requirement, School, Slot, SpecError, Timetable
from .scoring import ScoreBreakdown, score
from .solver import STATUS_NAMES, ModelBuilder, SolveSettings, configure, solve

ROOM_CHANGE_COST = 5


@dataclass(frozen=True)
class Change:
    kind: str  # unavailable | reassign | leave | add_lesson | set_max_per_week
    teacher: str = ""
    slots: str = ""
    to: str = ""
    class_id: str = ""
    subject_id: str = ""
    count: int = 1
    value: int = 0

    def describe(self) -> str:
        if self.kind == "unavailable":
            return f"Teacher {self.teacher} becomes unavailable {self.slots}"
        if self.kind == "leave":
            return f"Teacher {self.teacher} leaves; {self.to} takes over their classes"
        if self.kind == "reassign":
            scope = " ".join(x for x in (self.class_id, self.subject_id) if x) or "all classes"
            return f"{self.teacher}'s lessons ({scope}) move to teacher {self.to}"
        if self.kind == "add_lesson":
            return f"Class {self.class_id} gets {self.count} more {self.subject_id} lesson(s)"
        return f"Teacher {self.teacher} may now teach up to {self.value} lessons a week"


def load_changes(path: str | Path) -> list[Change]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise InputError([Issue("error", "bad-change", f"cannot read {path}: {e}")]) from e
    raw = (data or {}).get("changes") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise InputError([Issue("error", "bad-change", "expected a 'changes:' list", str(path))])
    out: list[Change] = []
    for i, item in enumerate(raw):
        where = f"{path}: changes[{i}]"
        if not isinstance(item, dict) or len(item) != 1:
            raise InputError(
                [Issue("error", "bad-change", "each change is a single-key mapping", where)]
            )
        ((kind, body),) = item.items()
        body = body or {}
        try:
            if kind == "unavailable":
                out.append(Change(kind, teacher=str(body["teacher"]), slots=str(body["slots"])))
            elif kind == "leave":
                out.append(Change(kind, teacher=str(body["teacher"]), to=str(body["replacement"])))
            elif kind == "reassign":
                out.append(
                    Change(
                        kind,
                        teacher=str(body["from"]),
                        to=str(body["to"]),
                        class_id=str(body.get("class", "")),
                        subject_id=str(body.get("subject", "")),
                    )
                )
            elif kind == "add_lesson":
                out.append(
                    Change(
                        kind,
                        class_id=str(body["class"]),
                        subject_id=str(body["subject"]),
                        count=int(body.get("count", 1)),
                        teacher=str(body.get("teacher", "")),
                    )
                )
            elif kind == "set_max_per_week":
                out.append(Change(kind, teacher=str(body["teacher"]), value=int(body["value"])))
            else:
                raise InputError(
                    [
                        Issue(
                            "error",
                            "bad-change",
                            f"unknown change '{kind}' (unavailable, leave, "
                            "reassign, add_lesson, set_max_per_week)",
                            where,
                        )
                    ]
                )
        except KeyError as e:
            raise InputError(
                [Issue("error", "bad-change", f"'{kind}' is missing {e.args[0]}", where)]
            ) from e
    return out


def apply_changes(school: School, changes: list[Change]) -> School:
    """Return the school as it will be after the changes (raises InputError if nonsense)."""
    cal = school.calendar
    teachers = dict(school.teachers)
    reqs = list(school.requirements)

    def need_teacher(tid: str, where: str) -> None:
        if tid not in teachers:
            raise InputError(
                [Issue("error", "unknown-teacher", f"teacher '{tid}' not found", where)]
            )

    for ch in changes:
        where = ch.describe()
        if ch.kind == "unavailable":
            need_teacher(ch.teacher, where)
            try:
                extra = cal.parse_slots(ch.slots)
            except SpecError as e:
                raise InputError([Issue("error", "bad-change", str(e), where)]) from e
            t = teachers[ch.teacher]
            teachers[ch.teacher] = replace(t, unavailable=t.unavailable | frozenset(extra))
        elif ch.kind in ("leave", "reassign"):
            need_teacher(ch.teacher, where)
            need_teacher(ch.to, where)
            if ch.kind == "leave":
                everything = frozenset(cal.parse_slots("*:*"))
                t = teachers[ch.teacher]
                teachers[ch.teacher] = replace(t, unavailable=t.unavailable | everything)
            for i, r in enumerate(reqs):
                if r.teacher_id != ch.teacher:
                    continue
                if ch.class_id and r.class_id != ch.class_id:
                    continue
                if ch.subject_id and r.subject_id != ch.subject_id:
                    continue
                dest = teachers[ch.to]
                if r.subject_id not in dest.subjects:
                    teachers[ch.to] = replace(dest, subjects=(*dest.subjects, r.subject_id))
                reqs[i] = replace(r, teacher_id=ch.to)
        elif ch.kind == "add_lesson":
            idx = next(
                (
                    i
                    for i, r in enumerate(reqs)
                    if r.class_id == ch.class_id and r.subject_id == ch.subject_id
                ),
                None,
            )
            if idx is None:
                if not ch.teacher:
                    raise InputError(
                        [
                            Issue(
                                "error",
                                "bad-change",
                                f"{ch.class_id} has no {ch.subject_id} lessons yet; say which "
                                "teacher takes them with 'teacher:'",
                                where,
                            )
                        ]
                    )
                need_teacher(ch.teacher, where)
                reqs.append(Requirement(ch.class_id, ch.subject_id, ch.teacher, ch.count))
            else:
                reqs[idx] = replace(reqs[idx], lessons=reqs[idx].lessons + ch.count)
        elif ch.kind == "set_max_per_week":
            need_teacher(ch.teacher, where)
            teachers[ch.teacher] = replace(teachers[ch.teacher], max_per_week=ch.value)
    return replace(school, teachers=teachers, requirements=tuple(reqs))


@dataclass
class Move:
    class_id: str
    subject_id: str
    kind: str  # "moved" | "added" | "teacher" | "room"
    before: Slot | None
    after: Slot | None
    detail: str = ""


@dataclass
class RepairResult:
    status: str
    school: School
    timetable: Timetable | None
    moves: list[Move] = field(default_factory=list)
    total_lessons: int = 0
    moved: int = 0
    added: int = 0
    teacher_changed: int = 0
    room_changes: int = 0
    minimal_proven: bool = False
    scratch_moved: int | None = None
    breakdown: ScoreBreakdown | None = None
    wall_time: float = 0.0
    stats: dict[str, Any] = field(default_factory=dict)


def _slot_map(timetable: Timetable) -> dict[tuple[str, str], set[Slot]]:
    out: dict[tuple[str, str], set[Slot]] = defaultdict(set)
    for e in timetable.events:
        out[(e.class_id, e.subject_id)].update(e.slots)
    return out


def count_moved(old: Timetable, new: Timetable) -> int:
    """Old lesson-periods that are no longer at the same (class, subject, slot)."""
    new_map = _slot_map(new)
    return sum(len(slots - new_map.get(key, set())) for key, slots in _slot_map(old).items())


def repair(
    school: School,
    old: Timetable,
    changes: list[Change],
    settings: SolveSettings | None = None,
    *,
    compare_scratch: bool = False,
) -> RepairResult:
    settings = settings or SolveSettings()
    started = time.perf_counter()
    new_school = apply_changes(school, changes)
    builder = ModelBuilder(new_school, soft=True)
    index = {r.key: i for i, r in enumerate(builder.reqs)}
    old_map = _slot_map(old)

    moved_terms: list[Any] = []
    for key, slots in old_map.items():
        ri = index.get(key)
        if ri is None:
            continue
        for s in slots:
            if (ri, s) in builder.x:
                moved_terms.append(1 - builder.x[(ri, s)])
    moved_expr = sum(moved_terms) if moved_terms else 0

    room_terms: list[Any] = []
    for e in old.events:
        ri = index.get((e.class_id, e.subject_id))
        if ri is None:
            continue
        s = (e.day, e.period)
        start_var = builder.b1.get((ri, s)) if e.length == 1 else builder.b2.get((ri, s))
        table = builder.e1 if e.length == 1 else builder.e2
        same_room = table.get((ri, s, e.room_id))
        if start_var is not None and same_room is not None:
            room_terms.append(start_var - same_room)

    builder.add_hint(old)
    model = builder.model
    soft_expr = sum(w * v for w, v in builder.soft_terms) if builder.soft_terms else 0

    # stage 1: fewest moved lessons
    model.minimize(moved_expr)
    solver = cp_model.CpSolver()
    half = max(1.0, settings.time_limit / 2)
    configure(solver, replace(settings, time_limit=half))
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return RepairResult(
            STATUS_NAMES.get(status, str(status)),
            new_school,
            None,
            wall_time=time.perf_counter() - started,
        )
    best_moved = round(solver.objective_value)
    proven = status == cp_model.OPTIMAL

    # stage 2: keep that minimum, then tidy up the soft score
    model.add(moved_expr <= best_moved)
    model.minimize(soft_expr + ROOM_CHANGE_COST * sum(room_terms) if room_terms else soft_expr)
    builder.add_hint(builder.extract(solver))
    solver2 = cp_model.CpSolver()
    configure(solver2, replace(settings, time_limit=max(1.0, settings.time_limit - half)))
    status2 = solver2.solve(model)
    use = solver2 if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE) else solver
    timetable = builder.extract(use)

    result = _diff(school, new_school, old, timetable)
    result.status = STATUS_NAMES.get(status2 if use is solver2 else status, "FEASIBLE")
    result.minimal_proven = proven
    result.breakdown = score(new_school, timetable)
    result.wall_time = time.perf_counter() - started
    if compare_scratch:
        scratch = solve(new_school, replace(settings, hint=None))
        if scratch.timetable is not None:
            result.scratch_moved = count_moved(old, scratch.timetable)
    return result


def _diff(old_school: School, new_school: School, old: Timetable, new: Timetable) -> RepairResult:
    old_map, new_map = _slot_map(old), _slot_map(new)
    moves: list[Move] = []
    moved = added = 0
    for key in sorted(set(old_map) | set(new_map)):
        before = sorted(old_map.get(key, set()) - new_map.get(key, set()))
        after = sorted(new_map.get(key, set()) - old_map.get(key, set()))
        for i, b in enumerate(before):
            if i < len(after):
                moves.append(Move(key[0], key[1], "moved", b, after[i]))
            else:
                moves.append(Move(key[0], key[1], "moved", b, None, "removed"))
            moved += 1
        for a in after[len(before) :]:
            moves.append(Move(key[0], key[1], "added", None, a))
            added += 1
    old_teacher = {r.key: r.teacher_id for r in old_school.requirements}
    teacher_changed = 0
    kept_events = {(e.class_id, e.subject_id, e.day, e.period, e.length): e for e in new.events}
    for e in old.events:
        r = new_school.requirement(e.class_id, e.subject_id)
        if r is None:
            continue
        match = kept_events.get((e.class_id, e.subject_id, e.day, e.period, e.length))
        if match is None:
            continue
        if old_teacher.get(r.key) != r.teacher_id:
            teacher_changed += e.length
            moves.append(
                Move(
                    e.class_id,
                    e.subject_id,
                    "teacher",
                    (e.day, e.period),
                    (e.day, e.period),
                    f"{old_teacher.get(r.key)} -> {r.teacher_id}",
                )
            )
        if match.room_id != e.room_id:
            moves.append(
                Move(
                    e.class_id,
                    e.subject_id,
                    "room",
                    (e.day, e.period),
                    (e.day, e.period),
                    f"{e.room_id} -> {match.room_id}",
                )
            )
    room_changes = sum(1 for m in moves if m.kind == "room")
    return RepairResult(
        status="",
        school=new_school,
        timetable=new,
        moves=moves,
        total_lessons=old.lesson_count(),
        moved=moved,
        added=added,
        teacher_changed=teacher_changed,
        room_changes=room_changes,
    )


def _unused(_: Event) -> None:  # pragma: no cover - keeps Event imported for type readers
    return None
