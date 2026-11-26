"""Static site generation: index, class/teacher/room pages, master grids, CSV and ICS."""

from __future__ import annotations

from pathlib import Path

from ..model import School, Timetable
from ..scoring import score
from ..validator import ValidationReport, validate
from . import ics as ics_mod
from .csvout import timetable_csv
from .pages import (
    Ctx,
    class_page,
    index_page,
    layout,
    master_page,
    room_page,
    teacher_page,
)
from .script import JS
from .style import build_css


def build_site(
    school: School,
    timetable: Timetable,
    out_dir: str | Path,
    *,
    report: ValidationReport | None = None,
) -> ValidationReport:
    """Write the whole site under ``out_dir`` and return the validation report used."""
    out = Path(out_dir)
    report = report or validate(school, timetable)
    ctx = Ctx(school, timetable, report)
    meta = dict(timetable.meta)
    breakdown = score(school, timetable)
    has_ics = ics_mod.supports_ics(school)

    def write(rel: str, text: str) -> None:
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="" if rel.endswith(".ics") else None)

    write("assets/style.css", build_css(len(school.subjects)))
    write("assets/app.js", JS)
    write("exports/timetable.csv", timetable_csv(school, timetable))

    title, body = index_page(ctx, breakdown, meta, has_ics)
    write("index.html", layout(ctx, title, body, "", "home", f"Timetables for {school.name}"))
    for by, fname, key in (
        ("class", "master.html", "master"),
        ("teacher", "master-teachers.html", "master-t"),
    ):
        title, body = master_page(ctx, by)
        write(fname, layout(ctx, title, body, "", key))

    for cid in school.classes:
        href = f"exports/ics/class-{cid}.ics" if has_ics else None
        title, body = class_page(ctx, cid, href)
        write(f"classes/{cid}.html", layout(ctx, title, body, "../", "classes"))
        if has_ics:
            write(
                f"exports/ics/class-{cid}.ics",
                ics_mod.build_ics(
                    school, timetable.by_class(cid), school.classes[cid].name, "class"
                ),
            )
    for tid in school.teachers:
        events = timetable.by_teacher(tid)
        if not events:
            continue
        href = f"exports/ics/teacher-{tid}.ics" if has_ics else None
        title, body = teacher_page(ctx, tid, href)
        write(f"teachers/{tid}.html", layout(ctx, title, body, "../", "teachers"))
        if has_ics:
            write(
                f"exports/ics/teacher-{tid}.ics",
                ics_mod.build_ics(school, events, school.teachers[tid].name, "teacher"),
            )
    specialist = {s.room_type for s in school.subjects.values()}
    for rid, room in school.rooms.items():
        if room.type in specialist:
            title, body = room_page(ctx, rid, None)
            write(f"rooms/{rid}.html", layout(ctx, title, body, "../", "rooms"))
    return report
