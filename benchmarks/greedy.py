"""A hand-rolled greedy timetabler, kept only to measure what it cannot do.

Strategy (what a first attempt, or a spreadsheet macro, usually does): take the lessons
that look hardest first (doubles, then teachers with the fewest free slots), put each in the
first slot where the class, teacher and room are free and the per-day limit holds. No
backtracking. Run:  python benchmarks/greedy.py examples/secondary
"""

from __future__ import annotations

import sys
from collections import defaultdict

from shule_timetable.loader import load_school
from shule_timetable.model import Event, School, Slot, Timetable
from shule_timetable.scoring import score
from shule_timetable.validator import validate


def greedy(school: School) -> tuple[Timetable, int]:
    cal = school.calendar
    class_busy: set[tuple[str, Slot]] = set()
    teacher_busy: set[tuple[str, Slot]] = set()
    room_busy: set[tuple[str, Slot]] = set()
    per_day: dict[tuple[str, str, int], int] = defaultdict(int)
    teacher_week: dict[str, int] = defaultdict(int)
    teacher_day: dict[tuple[str, int], int] = defaultdict(int)
    events: list[Event] = []
    unplaced = 0

    def free_slots(tid: str) -> int:
        return len([s for s in cal.slots if s not in school.teachers[tid].unavailable])

    # (priority, requirement, length) work items, hardest first
    items = []
    for r in school.requirements:
        items += [(0, free_slots(r.teacher_id), r, 2)] * r.doubles
        items += [(1, free_slots(r.teacher_id), r, 1)] * (r.lessons - 2 * r.doubles)
    items.sort(key=lambda x: (x[0], x[1]))

    for _, _, r, length in items:
        subject = school.subjects[r.subject_id]
        t = school.teachers[r.teacher_id]
        limit = school.subject_max_per_day(r.subject_id)
        home = school.classes[r.class_id].home_room
        placed = False
        for d, p in cal.slots:
            slots = [(d, p + i) for i in range(length)]
            if not all(s in cal.slots for s in slots):
                continue
            if length == 2 and cal.break_between(p, p + 1):
                continue
            if any(
                (r.class_id, s) in class_busy or (r.teacher_id, s) in teacher_busy for s in slots
            ):
                continue
            if any(s in t.unavailable for s in slots):
                continue
            if per_day[(r.class_id, r.subject_id, d)] + length > limit:
                continue
            if teacher_week[r.teacher_id] + length > t.max_per_week:
                continue
            if teacher_day[(r.teacher_id, d)] + length > t.max_per_day:
                continue
            room = home
            if school.uses_pool(r, is_double=length == 2):
                options = [
                    x.id
                    for x in school.pool_rooms_for(r)
                    if all((x.id, s) not in room_busy for s in slots)
                ]
                if not options:
                    continue
                room = options[0]
            for s in slots:
                class_busy.add((r.class_id, s))
                teacher_busy.add((r.teacher_id, s))
                room_busy.add((room, s))
            per_day[(r.class_id, r.subject_id, d)] += length
            teacher_week[r.teacher_id] += length
            teacher_day[(r.teacher_id, d)] += length
            events.append(Event(r.class_id, r.subject_id, r.teacher_id, room, d, p, length))
            placed = True
            break
        if not placed:
            unplaced += length
        _ = subject
    return Timetable(tuple(events)), unplaced


def main() -> None:
    school = load_school(sys.argv[1])
    tt, unplaced = greedy(school)
    total = sum(r.lessons for r in school.requirements)
    rep = validate(school, tt)
    print(f"{school.name}")
    print(f"required lesson periods: {total}")
    print(f"placed by greedy:        {total - unplaced}")
    print(f"left unplaced:           {unplaced} ({100 * unplaced / total:.1f}%)")
    only_counts = [r for r in rep.rules if r.id not in ("lesson-counts", "doubles") and not r.ok]
    print(
        f"other hard-rule violations among what was placed: {sum(len(r.violations) for r in only_counts)}"
    )
    classes_short = {
        r.class_id
        for r in school.requirements
        if sum(
            e.length for e in tt.events if e.class_id == r.class_id and e.subject_id == r.subject_id
        )
        < r.lessons
    }
    print(f"soft-rule penalty of what it built: {score(school, tt).total}")
    print(f"classes with at least one subject short: {len(classes_short)} of {len(school.classes)}")


if __name__ == "__main__":
    main()
