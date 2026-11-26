"""Read ``school.yaml`` plus the five CSV files into a :class:`School`.

Every problem is collected (not just the first) and reported with a file:line pointer, so
a deputy head can fix the whole lot in one editing pass.
"""

from __future__ import annotations

import csv
import datetime as dt
import difflib
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from .issues import InputError, Issue, errors_of
from .model import (
    HOME,
    Break,
    Calendar,
    Limits,
    Period,
    Requirement,
    Room,
    School,
    SchoolClass,
    SpecError,
    Subject,
    Teacher,
    Term,
    Weights,
)

FILES = (
    "school.yaml",
    "subjects.csv",
    "rooms.csv",
    "classes.csv",
    "teachers.csv",
    "requirements.csv",
)
_TIME = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
_TRUE = {"yes", "true", "1", "y"}
_FALSE = {"no", "false", "0", "n", ""}


def suggest(name: str, options: Iterable[str]) -> str:
    match = difflib.get_close_matches(name, list(options), n=1, cutoff=0.6)
    return f" Did you mean '{match[0]}'?" if match else ""


class _Collector:
    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def error(self, code: str, message: str, where: str = "") -> None:
        self.issues.append(Issue("error", code, message, where))

    def warn(self, code: str, message: str, where: str = "") -> None:
        self.issues.append(Issue("warning", code, message, where))


def _read_csv(
    path: Path, required: tuple[str, ...], optional: tuple[str, ...], c: _Collector
) -> list[tuple[int, dict[str, str]]]:
    if not path.exists():
        c.error("missing-file", f"{path.name} not found in {path.parent}", path.name)
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [h for h in required if h not in header]
        if missing:
            c.error(
                "missing-column",
                f"missing column(s) {', '.join(missing)}; the header row is: {', '.join(header)}",
                f"{path.name}:1",
            )
            return []
        for h in header:
            if h and h not in required and h not in optional:
                c.warn(
                    "unknown-column",
                    f"column '{h}' is not used.{suggest(h, [*required, *optional])}",
                    f"{path.name}:1",
                )
        rows: list[tuple[int, dict[str, str]]] = []
        for line, raw in enumerate(reader, start=2):
            row = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k}
            if not any(row.values()):
                continue
            rows.append((line, row))
        return rows


def _int(
    value: str,
    field: str,
    where: str,
    c: _Collector,
    *,
    minimum: int = 0,
    default: int | None = None,
) -> int | None:
    if value == "" and default is not None:
        return default
    try:
        n = int(value)
    except ValueError:
        c.error("bad-number", f"{field} must be a whole number, got '{value}'", where)
        return None
    if n < minimum:
        c.error("bad-number", f"{field} must be at least {minimum}, got {n}", where)
        return None
    return n


def _bool(value: str, field: str, where: str, c: _Collector) -> bool:
    v = value.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    c.error("bad-flag", f"{field} must be yes or no, got '{value}'", where)
    return False


def _parse_calendar(data: dict[str, Any], c: _Collector) -> Calendar | None:
    where = "school.yaml"
    days = data.get("days")
    if not isinstance(days, list) or not days or not all(isinstance(d, str) for d in days):
        c.error("bad-days", "'days' must be a list such as [Mon, Tue, Wed, Thu, Fri]", where)
        return None
    raw_periods = data.get("periods")
    if not isinstance(raw_periods, list) or not raw_periods:
        c.error("bad-periods", "'periods' must be a list of {label, start, end}", where)
        return None
    periods: list[Period] = []
    for i, p in enumerate(raw_periods):
        if not isinstance(p, dict) or not {"label", "start", "end"} <= set(p):
            c.error("bad-periods", f"periods[{i}] needs label, start and end", where)
            continue
        start, end = str(p["start"]), str(p["end"])
        for fld, val in (("start", start), ("end", end)):
            if not _TIME.match(val):
                c.error("bad-time", f"periods[{i}].{fld} must be HH:MM, got '{val}'", where)
        periods.append(Period(str(p["label"]), start, end))
    labels = [p.label for p in periods]
    if len(set(labels)) != len(labels):
        c.error("bad-periods", "period labels must be unique", where)
    if c.issues and errors_of(c.issues):
        return None
    cal0 = Calendar(tuple(days), tuple(periods))

    breaks: list[Break] = []
    for i, b in enumerate(data.get("breaks") or []):
        try:
            after = cal0.period_index(str(b["after"]))
        except (KeyError, TypeError):
            c.error("bad-break", f"breaks[{i}] needs 'after' (a period label)", where)
            continue
        except SpecError as e:
            c.error("bad-break", f"breaks[{i}].after: {e}", where)
            continue
        if after >= len(periods) - 1:
            c.error(
                "bad-break", f"breaks[{i}] comes after the last period, so it has no effect", where
            )
            continue
        breaks.append(Break(after, str(b.get("name", "Break")), bool(b.get("long", False))))

    lengths = [len(periods)] * len(days)
    for day, n in (data.get("short_days") or {}).items():
        try:
            d = cal0.day_index(str(day))
        except SpecError as e:
            c.error("bad-short-day", f"short_days: {e}", where)
            continue
        if not isinstance(n, int) or not 1 <= n <= len(periods):
            c.error(
                "bad-short-day", f"short_days.{day} must be between 1 and {len(periods)}", where
            )
            continue
        lengths[d] = n

    blocked: set[tuple[int, int]] = set()
    for spec in data.get("blocked") or []:
        try:
            blocked |= cal0.parse_slots(str(spec))
        except SpecError as e:
            c.error("bad-blocked", f"blocked: {e}", where)
    return Calendar(tuple(days), tuple(periods), tuple(breaks), tuple(lengths), frozenset(blocked))


def _parse_weights_limits(
    data: dict[str, Any], cal: Calendar, c: _Collector
) -> tuple[Weights, Limits, frozenset[tuple[int, int]]]:
    where = "school.yaml"
    weights = Weights()
    raw_w = data.get("weights") or {}
    if not isinstance(raw_w, dict):
        c.error("bad-weights", "'weights' must be a mapping of name: number", where)
        raw_w = {}
    kwargs: dict[str, int] = {}
    for k, v in raw_w.items():
        if k not in Weights.__dataclass_fields__:
            c.error(
                "bad-weights",
                f"unknown weight '{k}'.{suggest(str(k), Weights.__dataclass_fields__)}",
                where,
            )
        elif not isinstance(v, int) or isinstance(v, bool) or v < 0:
            c.error("bad-weights", f"weight '{k}' must be a whole number >= 0, got {v!r}", where)
        else:
            kwargs[k] = v
    weights = Weights(**{**weights.as_dict(), **kwargs})

    limits = Limits()
    raw_l = data.get("limits") or {}
    lk: dict[str, Any] = {}
    for k, v in raw_l.items():
        if k == "morning_until":
            try:
                lk[k] = cal.period_index(str(v))
            except SpecError as e:
                c.error("bad-limits", f"limits.morning_until: {e}", where)
        elif k in ("max_per_subject_per_day", "max_consecutive_lessons"):
            if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                c.error("bad-limits", f"limits.{k} must be a whole number >= 1", where)
            else:
                lk[k] = v
        else:
            c.error("bad-limits", f"unknown limit '{k}'", where)
    limits = Limits(**{**limits.__dict__, **lk})

    light: set[tuple[int, int]] = set()
    for spec in data.get("light_slots") or []:
        try:
            light |= cal.parse_slots(str(spec))
        except SpecError as e:
            c.error("bad-light-slots", f"light_slots: {e}", where)
    return weights, limits, frozenset(s for s in light if cal.is_valid(s))


def _parse_term(data: dict[str, Any], c: _Collector) -> Term | None:
    raw = data.get("term")
    if raw is None:
        return None
    try:
        start = raw["start"]
        if isinstance(start, str):
            start = dt.date.fromisoformat(start)
        if not isinstance(start, dt.date):
            raise ValueError
        weeks = int(raw["weeks"])
        if weeks < 1:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        c.error("bad-term", "term must look like {start: 2026-01-05, weeks: 13}", "school.yaml")
        return None
    return Term(start, weeks)


def load_with_issues(directory: str | Path) -> tuple[School | None, list[Issue]]:
    """Load a school; returns (school or None if there are errors, all issues found)."""
    root = Path(directory)
    c = _Collector()
    if not root.is_dir():
        c.error("missing-dir", f"{root} is not a directory")
        return None, c.issues

    cfg_path = root / "school.yaml"
    data: dict[str, Any] = {}
    if not cfg_path.exists():
        c.error("missing-file", f"school.yaml not found in {root}", "school.yaml")
    else:
        try:
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            line = f":{mark.line + 1}" if mark else ""
            c.error(
                "bad-yaml",
                f"could not parse YAML ({getattr(e, 'problem', e)})",
                f"school.yaml{line}",
            )
            loaded = None
        if isinstance(loaded, dict):
            data = loaded
        elif loaded is not None:
            c.error("bad-yaml", "school.yaml must be a mapping at the top level", "school.yaml")

    cal = _parse_calendar(data, c) if data else None
    weights, limits, light = (Weights(), Limits(), frozenset[tuple[int, int]]())
    if cal:
        weights, limits, light = _parse_weights_limits(data, cal, c)
    term = _parse_term(data, c) if data else None
    name = str(data.get("name", "Unnamed school"))
    synthetic = bool(data.get("synthetic", False))

    subjects = _load_subjects(root / "subjects.csv", c)
    rooms = _load_rooms(root / "rooms.csv", c)
    classes = _load_classes(root / "classes.csv", rooms, subjects, c)
    teachers = _load_teachers(root / "teachers.csv", subjects, cal, c)
    requirements = _load_requirements(
        root / "requirements.csv", classes, subjects, teachers, limits, c
    )

    if cal is None or errors_of(c.issues):
        return None, c.issues
    school = School(
        name=name,
        calendar=cal,
        subjects=subjects,
        teachers=teachers,
        rooms=rooms,
        classes=classes,
        requirements=tuple(requirements),
        weights=weights,
        limits=limits,
        light_slots=light,
        term=term,
        synthetic=synthetic,
    )
    _cross_checks(school, c)
    if errors_of(c.issues):
        return None, c.issues
    return school, c.issues


def load_school(directory: str | Path) -> School:
    school, issues = load_with_issues(directory)
    if school is None:
        raise InputError(issues)
    return school


def _load_subjects(path: Path, c: _Collector) -> dict[str, Subject]:
    rows = _read_csv(
        path,
        ("id", "name"),
        ("room_type", "room_use", "doubles", "heavy", "avoid_edges", "max_per_day"),
        c,
    )
    out: dict[str, Subject] = {}
    for line, row in rows:
        where = f"{path.name}:{line}"
        sid = row["id"]
        if not sid:
            c.error("missing-id", "subject id is empty", where)
            continue
        if sid in out:
            c.error("duplicate-id", f"subject id '{sid}' appears twice", where)
            continue
        room_use = (row.get("room_use") or "all").lower()
        if room_use not in ("all", "doubles"):
            c.error("bad-room-use", f"room_use must be 'all' or 'doubles', got '{room_use}'", where)
            room_use = "all"
        doubles = _int(row.get("doubles", ""), "doubles", where, c, default=0) or 0
        max_day = _int(row.get("max_per_day", ""), "max_per_day", where, c, minimum=1, default=0)
        out[sid] = Subject(
            id=sid,
            name=row["name"] or sid,
            room_type=row.get("room_type") or HOME,
            room_use=room_use,
            doubles=doubles,
            heavy=_bool(row.get("heavy", ""), "heavy", where, c),
            avoid_edges=_bool(row.get("avoid_edges", ""), "avoid_edges", where, c),
            max_per_day=max_day or None,
        )
    return out


def _load_rooms(path: Path, c: _Collector) -> dict[str, Room]:
    rows = _read_csv(path, ("id", "name", "type", "capacity"), (), c)
    out: dict[str, Room] = {}
    for line, row in rows:
        where = f"{path.name}:{line}"
        rid = row["id"]
        if rid in out:
            c.error("duplicate-id", f"room id '{rid}' appears twice", where)
            continue
        cap = _int(row["capacity"], "capacity", where, c, minimum=1)
        if cap is None or not rid:
            continue
        out[rid] = Room(rid, row["name"] or rid, row["type"], cap)
    return out


def _load_classes(
    path: Path, rooms: dict[str, Room], subjects: dict[str, Subject], c: _Collector
) -> dict[str, SchoolClass]:
    rows = _read_csv(path, ("id", "name", "size", "home_room"), (), c)
    out: dict[str, SchoolClass] = {}
    used_homes: dict[str, str] = {}
    subject_types = {s.room_type for s in subjects.values()}
    for line, row in rows:
        where = f"{path.name}:{line}"
        cid = row["id"]
        if cid in out:
            c.error("duplicate-id", f"class id '{cid}' appears twice", where)
            continue
        size = _int(row["size"], "size", where, c, minimum=1)
        home = row["home_room"]
        if home not in rooms:
            c.error(
                "unknown-room",
                f"class {cid} has home_room '{home}', which is not in rooms.csv.{suggest(home, rooms)}",
                where,
            )
            continue
        if home in used_homes:
            c.error(
                "shared-home-room",
                f"classes {used_homes[home]} and {cid} both use home room '{home}'; "
                "give each class its own classroom",
                where,
            )
            continue
        if rooms[home].type in subject_types:
            c.error(
                "home-room-type-clash",
                f"home room '{home}' has type '{rooms[home].type}', which a subject also uses for "
                "specialist lessons; use a different type for classrooms",
                where,
            )
        used_homes[home] = cid
        if size is None:
            continue
        if rooms[home].capacity < size:
            c.warn(
                "home-room-small",
                f"class {cid} has {size} learners but its home room {home} holds {rooms[home].capacity}",
                where,
            )
        out[cid] = SchoolClass(cid, row["name"] or cid, size, home)
    return out


def _load_teachers(
    path: Path, subjects: dict[str, Subject], cal: Calendar | None, c: _Collector
) -> dict[str, Teacher]:
    rows = _read_csv(
        path, ("id", "name", "subjects", "max_per_week"), ("max_per_day", "unavailable"), c
    )
    out: dict[str, Teacher] = {}
    for line, row in rows:
        where = f"{path.name}:{line}"
        tid = row["id"]
        if tid in out:
            c.error("duplicate-id", f"teacher id '{tid}' appears twice", where)
            continue
        subs = tuple(s.strip() for s in re.split(r"[;|]", row["subjects"]) if s.strip())
        for s in subs:
            if s not in subjects:
                c.error(
                    "unknown-subject",
                    f"teacher {tid} lists subject '{s}', which is not in subjects.csv."
                    f"{suggest(s, subjects)}",
                    where,
                )
        weekly = _int(row["max_per_week"], "max_per_week", where, c, minimum=1)
        daily = _int(row.get("max_per_day", ""), "max_per_day", where, c, minimum=1, default=99)
        unavailable: frozenset[tuple[int, int]] = frozenset()
        if row.get("unavailable") and cal is not None:
            try:
                unavailable = frozenset(cal.parse_slots(row["unavailable"]))
            except SpecError as e:
                c.error("bad-unavailable", f"teacher {tid} unavailable: {e}", where)
        if weekly is None or daily is None or not tid:
            continue
        out[tid] = Teacher(tid, row["name"] or tid, subs, weekly, daily, unavailable)
    return out


def _load_requirements(
    path: Path,
    classes: dict[str, SchoolClass],
    subjects: dict[str, Subject],
    teachers: dict[str, Teacher],
    limits: Limits,
    c: _Collector,
) -> list[Requirement]:
    rows = _read_csv(path, ("class", "subject", "teacher", "lessons"), ("doubles",), c)
    out: list[Requirement] = []
    seen: dict[tuple[str, str], int] = {}
    for line, row in rows:
        where = f"{path.name}:{line}"
        cid, sid, tid = row["class"], row["subject"], row["teacher"]
        ok = True
        if cid not in classes:
            c.error(
                "unknown-class",
                f"class '{cid}' is not in classes.csv.{suggest(cid, classes)}",
                where,
            )
            ok = False
        if sid not in subjects:
            c.error(
                "unknown-subject",
                f"subject '{sid}' is not in subjects.csv.{suggest(sid, subjects)}",
                where,
            )
            ok = False
        if tid not in teachers:
            c.error(
                "unknown-teacher",
                f"teacher '{tid}' is not in teachers.csv.{suggest(tid, teachers)}",
                where,
            )
            ok = False
        lessons = _int(row["lessons"], "lessons", where, c, minimum=1)
        if lessons is None or not ok:
            continue
        default_doubles = subjects[sid].doubles
        doubles = _int(row.get("doubles", ""), "doubles", where, c, default=default_doubles)
        if doubles is None:
            continue
        if 2 * doubles > lessons:
            c.error(
                "too-many-doubles",
                f"{cid} {sid}: {doubles} double lesson(s) need {2 * doubles} periods but only "
                f"{lessons} lessons a week are required",
                where,
            )
            continue
        if doubles > 0 and subjects[sid].max_per_day is None and limits.max_per_subject_per_day < 2:
            c.error(
                "double-vs-daily-limit",
                f"{cid} {sid} needs a double lesson but max_per_subject_per_day is "
                f"{limits.max_per_subject_per_day}",
                where,
            )
            continue
        if (cid, sid) in seen:
            c.error(
                "duplicate-requirement",
                f"class {cid} subject {sid} is already listed on line {seen[(cid, sid)]}",
                where,
            )
            continue
        seen[(cid, sid)] = line
        out.append(Requirement(cid, sid, tid, lessons, doubles))
    return out


def _cross_checks(school: School, c: _Collector) -> None:
    """Checks that need the whole school (qualification, unused subjects, room types)."""
    taught: dict[str, set[str]] = {}
    for r in school.requirements:
        taught.setdefault(r.teacher_id, set()).add(r.subject_id)
        t = school.teachers[r.teacher_id]
        if r.subject_id not in t.subjects:
            sname = school.subjects[r.subject_id].name
            c.error(
                "teacher-not-qualified",
                f"Teacher {t.id} ({t.name}) is assigned {sname} for class {r.class_id}, but "
                f"{t.id}'s subjects list ({'; '.join(t.subjects) or 'empty'}) does not include "
                f"{r.subject_id}",
                "requirements.csv",
            )
        subject = school.subjects[r.subject_id]
        if subject.room_type != HOME:
            pool = school.pool_rooms_for(r)
            if not pool:
                size = school.classes[r.class_id].size
                of_type = [x for x in school.rooms.values() if x.type == subject.room_type]
                if not of_type:
                    c.error(
                        "no-room-of-type",
                        f"{subject.name} needs a '{subject.room_type}' room but rooms.csv has none",
                        "rooms.csv",
                    )
                else:
                    biggest = max(x.capacity for x in of_type)
                    c.error(
                        "class-too-big-for-room",
                        f"Class {r.class_id} has {size} learners but the largest "
                        f"'{subject.room_type}' room holds {biggest}, so {subject.name} cannot "
                        "be scheduled for it",
                        "rooms.csv",
                    )
    needed = {r.subject_id for r in school.requirements}
    for t in school.teachers.values():
        for s in t.subjects:
            if s in school.subjects and s not in needed:
                c.warn(
                    "subject-unused",
                    f"Teacher {t.id} teaches {school.subjects[s].name} but no class needs "
                    f"{school.subjects[s].name}",
                    "teachers.csv",
                )
        if t.id not in taught:
            c.warn(
                "teacher-idle", f"Teacher {t.id} ({t.name}) has no lessons assigned", "teachers.csv"
            )
    for cid in school.classes:
        if not any(r.class_id == cid for r in school.requirements):
            c.warn(
                "class-empty", f"Class {cid} has no lessons in requirements.csv", "requirements.csv"
            )
