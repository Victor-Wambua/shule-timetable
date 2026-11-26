"""Infeasibility pre-checks: cheap arithmetic that explains *why* before the solver runs.

Each check looks at one resource (a class, a teacher, a room type) and compares what is
asked of it with what it can give. They are sufficient-not-necessary: passing them does
not guarantee a timetable exists, but failing any of them proves none does, and the
message says exactly which numbers do not add up.
"""

from __future__ import annotations

from collections import defaultdict

from .issues import Issue
from .model import HOME, School, Slot


def run_prechecks(school: School) -> list[Issue]:
    issues: list[Issue] = []
    for check in (
        _class_load,
        _teacher_load,
        _per_day_limits,
        _doubles_possible,
        _room_capacity,
        _class_teacher_availability,
    ):
        issues.extend(check(school))
    return issues


def _err(code: str, message: str, where: str = "") -> Issue:
    return Issue("error", code, message, where)


def _class_load(school: School) -> list[Issue]:
    n_slots = len(school.calendar.slots)
    out = []
    for cid, klass in school.classes.items():
        need = sum(r.lessons for r in school.requirements if r.class_id == cid)
        if need > n_slots:
            out.append(
                _err(
                    "class-over-slots",
                    f"Class {klass.name} needs {need} lessons/week but only {n_slots} slots exist "
                    f"({need - n_slots} too many). Remove lessons in requirements.csv or add "
                    "periods in school.yaml.",
                    "requirements.csv",
                )
            )
    return out


def _available_slots(school: School, teacher_id: str) -> list[Slot]:
    t = school.teachers[teacher_id]
    return [s for s in school.calendar.slots if s not in t.unavailable]


def _teacher_load(school: School) -> list[Issue]:
    out = []
    for tid, t in school.teachers.items():
        load = sum(r.lessons for r in school.teacher_requirements(tid))
        if load == 0:
            continue
        avail = _available_slots(school, tid)
        if load > t.max_per_week:
            out.append(
                _err(
                    "teacher-over-max",
                    f"Teacher {tid} ({t.name}) is assigned {load} lessons/week but max_per_week "
                    f"is {t.max_per_week}. Move {load - t.max_per_week} lesson(s) to another "
                    "teacher or raise the limit.",
                    "teachers.csv",
                )
            )
        if load > len(avail):
            out.append(
                _err(
                    "teacher-over-availability",
                    f"Teacher {tid} ({t.name}) is assigned {load} lessons/week but is available "
                    f"in only {len(avail)} slots ({len(t.unavailable & set(school.calendar.slots))} "
                    "marked unavailable).",
                    "teachers.csv",
                )
            )
        per_day = defaultdict(int)
        for d, _p in avail:
            per_day[d] += 1
        daily_cap = sum(min(t.max_per_day, n) for n in per_day.values())
        if load <= len(avail) and load > daily_cap:
            out.append(
                _err(
                    "teacher-over-daily",
                    f"Teacher {tid} ({t.name}) is assigned {load} lessons/week but with at most "
                    f"{t.max_per_day} a day and the current availability can teach {daily_cap}.",
                    "teachers.csv",
                )
            )
    return out


def _active_days(school: School) -> list[int]:
    return [d for d in range(len(school.calendar.days)) if school.calendar.valid_periods(d)]


def _per_day_limits(school: School) -> list[Issue]:
    out = []
    days = len(_active_days(school))
    for r in school.requirements:
        limit = school.subject_max_per_day(r.subject_id)
        if r.lessons > limit * days:
            sname = school.subjects[r.subject_id].name
            out.append(
                _err(
                    "subject-over-daily-limit",
                    f"Class {r.class_id} needs {r.lessons} {sname} lessons/week but at most "
                    f"{limit} a day over {days} days allows {limit * days}.",
                    "requirements.csv",
                )
            )
    return out


def _doubles_possible(school: School) -> list[Issue]:
    out = []
    cal = school.calendar
    for r in school.requirements:
        if r.doubles == 0:
            continue
        t = school.teachers[r.teacher_id]
        sname = school.subjects[r.subject_id].name
        starts = [
            (d, p)
            for d in range(len(cal.days))
            for p in cal.double_starts(d)
            if (d, p) not in t.unavailable and (d, p + 1) not in t.unavailable
        ]
        days_with = {d for d, _ in starts}
        per_day = max(1, school.subject_max_per_day(r.subject_id) // 2)
        capacity = len(days_with) * per_day
        if r.doubles > capacity:
            out.append(
                _err(
                    "doubles-impossible",
                    f"Class {r.class_id} needs {r.doubles} double {sname} lesson(s), but teacher "
                    f"{r.teacher_id} has two consecutive free periods (with no break between) on "
                    f"only {len(days_with)} day(s), which fits {capacity}.",
                    "requirements.csv",
                )
            )
    return out


def _room_capacity(school: School) -> list[Issue]:
    """Hall-style check per room type: lessons needing a room vs room-slots on offer."""
    n_slots = len(school.calendar.slots)
    demand: dict[str, list[tuple[frozenset[str], int, str]]] = defaultdict(list)
    for r in school.requirements:
        subject = school.subjects[r.subject_id]
        if subject.room_type == HOME:
            periods = 0
        elif subject.room_use == "all":
            periods = r.lessons
        else:
            periods = 2 * r.doubles
        if periods == 0:
            continue
        eligible = frozenset(x.id for x in school.pool_rooms_for(r))
        if not eligible:
            continue  # reported as an input error by the loader
        demand[subject.room_type].append((eligible, periods, r.class_id))
    out = []
    for rtype, entries in demand.items():
        for room_set in {e[0] for e in entries}:
            asked = sum(p for elig, p, _ in entries if elig <= room_set)
            offered = len(room_set) * n_slots
            if asked > offered:
                names = ", ".join(sorted(school.rooms[i].name for i in room_set))
                out.append(
                    _err(
                        "room-over-capacity",
                        f"Rooms of type '{rtype}' ({names}): classes need {asked} room-periods a "
                        f"week but {len(room_set)} room(s) x {n_slots} slots = {offered}. Add a "
                        "room or reduce practical lessons.",
                        "rooms.csv",
                    )
                )
    return out


def _class_teacher_availability(school: School) -> list[Issue]:
    """Can each class's lessons be matched to slots its teachers are free in?

    A bipartite matching (lessons -> slots). If it falls short, the set of lessons stuck
    in the failed search is a Hall violator, which we describe in words.
    """
    out = []
    slots = list(school.calendar.slots)
    for cid, klass in school.classes.items():
        lessons: list[tuple[str, str]] = []  # (teacher, subject name)
        for r in school.requirements:
            if r.class_id == cid:
                lessons.extend([(r.teacher_id, school.subjects[r.subject_id].name)] * r.lessons)
        if not lessons or len(lessons) > len(slots):
            continue
        adj = [
            [i for i, s in enumerate(slots) if s not in school.teachers[t].unavailable]
            for t, _ in lessons
        ]
        match_slot: dict[int, int] = {}

        def try_assign(
            u: int,
            seen: set[int],
            adj: list[list[int]] = adj,
            match_slot: dict[int, int] = match_slot,
        ) -> bool:
            for v in adj[u]:
                if v in seen:
                    continue
                seen.add(v)
                if v not in match_slot or try_assign(match_slot[v], seen):
                    match_slot[v] = u
                    return True
            return False

        stuck: set[int] | None = None
        for u in range(len(lessons)):
            seen: set[int] = set()
            if not try_assign(u, seen):
                # lessons reachable by alternating paths from u form a Hall violator
                stuck = {u} | {match_slot[v] for v in seen if v in match_slot}
                break
        if stuck is not None:
            teachers = sorted({lessons[i][0] for i in stuck})
            nbrs = {v for i in stuck for v in adj[i]}
            out.append(
                _err(
                    "class-teacher-availability",
                    f"Class {klass.name}: {len(stuck)} lessons taught by "
                    f"{', '.join(teachers)} can only go in {len(nbrs)} slot(s) where those "
                    "teachers are free, so they cannot all be placed. Relax the unavailability "
                    "of one of these teachers or move a lesson to another teacher.",
                    "teachers.csv",
                )
            )
    return out
