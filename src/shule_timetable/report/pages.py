"""HTML for the static site. Plain string building with every value escaped."""

from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Sequence

from ..explain import binding_constraints
from ..model import Event, School, Timetable
from ..scoring import ScoreBreakdown
from ..validator import ValidationReport

LOGO = (
    '<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
    '<rect x="2" y="2" width="28" height="28" rx="6" fill="#fca311"/>'
    '<g fill="#14213d"><rect x="6" y="6" width="6" height="6" rx="1.5"/>'
    '<rect x="13" y="6" width="6" height="6" rx="1.5" opacity=".35"/>'
    '<rect x="20" y="6" width="6" height="6" rx="1.5" opacity=".35"/>'
    '<rect x="6" y="13" width="6" height="6" rx="1.5" opacity=".35"/>'
    '<rect x="13" y="13" width="13" height="6" rx="1.5"/>'
    '<rect x="6" y="20" width="6" height="6" rx="1.5" opacity=".35"/>'
    '<rect x="13" y="20" width="6" height="6" rx="1.5" opacity=".35"/>'
    '<rect x="20" y="20" width="6" height="6" rx="1.5"/></g></svg>'
)
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect x='2' y='2' width='28' height='28' rx='6' fill='%23fca311'/%3E"
    "%3Crect x='6' y='6' width='6' height='6' rx='1.5' fill='%2314213d'/%3E"
    "%3Crect x='13' y='13' width='13' height='6' rx='1.5' fill='%2314213d'/%3E"
    "%3Crect x='20' y='20' width='6' height='6' rx='1.5' fill='%2314213d'/%3E%3C/svg%3E"
)


def esc(x: object) -> str:
    return html.escape(str(x), quote=True)


class Ctx:
    """What every page needs to know about the school and where it is in the site."""

    def __init__(self, school: School, timetable: Timetable, report: ValidationReport) -> None:
        self.school = school
        self.tt = timetable
        self.report = report
        self.subject_idx = {sid: i for i, sid in enumerate(school.subjects)}

    def sclass(self, subject_id: str) -> str:
        i = self.subject_idx[subject_id]
        return f"s{i} p{i % 8}"


def layout(ctx: Ctx, title: str, body: str, root: str, active: str, desc: str = "") -> str:
    school = ctx.school
    nav = [
        ("index.html", "Home", "home"),
        ("master.html", "Master grid", "master"),
        ("master-teachers.html", "By teacher", "master-t"),
        ("index.html#classes", "Classes", "classes"),
        ("index.html#teachers", "Teachers", "teachers"),
        ("index.html#rooms", "Rooms", "rooms"),
    ]
    links = "".join(
        f'<a href="{root}{href}"{" aria-current=page" if key == active else ""}>{esc(label)}</a>'
        for href, label, key in nav
    )
    tick = "&#10003;" if ctx.report.ok else "&#10007;"
    verdict = f'<span class="tick">{tick}</span> Independent validator: ' + (
        f"no violations in {ctx.report.checks:,} checks."
        if ctx.report.ok
        else f"{len(ctx.report.violations)} violation(s) found."
    )
    sample = " Synthetic sample data." if school.synthetic else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - {esc(school.name)}</title>
<meta name="description" content="{esc(desc or title)}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
<a class="skip" href="#main">Skip to the timetable</a>
<header class="top"><div class="top-inner">
<a class="brand" href="{root}index.html">{LOGO}<span>Shule Timetable</span></a>
<nav class="nav" aria-label="Sections">{links}</nav>
</div></header>
<main id="main">
{body}
</main>
<footer>{verdict}{sample} <span class="no-print">Built by Shule Timetable.</span>
<a class="no-print" href="{root}index.html#proof">Proof panel</a></footer>
<script src="{root}assets/app.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------------- grids
def _break_label(school: School, p: int) -> str:
    cal = school.calendar
    name = next((b.name for b in cal.breaks if b.after == p - 1), "Break")
    return f"{name} {cal.periods[p - 1].end}&ndash;{cal.periods[p].start}"


def _cell(ctx: Ctx, e: Event, perspective: str) -> str:
    s = ctx.school
    subject = s.subjects[e.subject_id].name
    klass = s.classes[e.class_id].name
    room = s.rooms[e.room_id].name
    teacher = s.teachers[e.teacher_id].name
    if perspective == "class":
        title, sub = subject, f"{teacher} &middot; {esc(room)}"
        sub = f"{esc(teacher)} &middot; {esc(room)}"
    elif perspective == "teacher":
        title, sub = klass, f"{esc(subject)} &middot; {esc(room)}"
    else:
        title, sub = klass, f"{esc(subject)} &middot; {esc(teacher)}"
    when = ctx.school.calendar.label((e.day, e.period))
    span = " (double lesson)" if e.length == 2 else ""
    label = f"{when}: {subject}, {klass}, {teacher}, {room}{span}"
    return (
        f'<span class="cell {ctx.sclass(e.subject_id)}" role="group" aria-label="{esc(label)}">'
        f'<span class="t">{esc(title)}</span><span class="s">{sub}</span></span>'
    )


def weekly_grid(ctx: Ctx, events: Sequence[Event], perspective: str, caption: str) -> str:
    school = ctx.school
    cal = school.calendar
    start_at = {(e.day, e.period): e for e in events}
    covered = {(e.day, e.period + 1) for e in events if e.length == 2}
    head = "".join(f'<th scope="col">{esc(d)}</th>' for d in cal.days)
    rows = [
        f'<tr><td class="sr-only">Period</td>{head}</tr>'.replace("<td", "<th").replace(
            "</td>", "</th>"
        )
    ]
    ncols = len(cal.days) + 1
    for p, per in enumerate(cal.periods):
        if p > 0 and cal.break_between(p - 1, p):
            rows.append(
                f'<tr class="break"><th colspan="{ncols}">{_break_label(school, p)}</th></tr>'
            )
        cells = [
            f'<th scope="row" class="period">{esc(per.label)}<small>{esc(per.start)}</small></th>'
        ]
        for d in range(len(cal.days)):
            slot = (d, p)
            if slot in covered:
                continue
            if p >= cal.day_lengths[d]:
                cells.append('<td class="off">&mdash;</td>')
            elif slot in cal.blocked:
                cells.append('<td class="blocked">No lessons</td>')
            elif slot in start_at:
                e = start_at[slot]
                span = f' rowspan="{e.length}"' if e.length == 2 else ""
                cells.append(f'<td class="lesson"{span}>{_cell(ctx, e, perspective)}</td>')
            else:
                cells.append('<td class="free"><span class="sr-only">Free</span></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f'<table class="grid"><caption class="sr-only">{esc(caption)}</caption>'
        + "".join(rows)
        + "</table>"
    )


def day_list(ctx: Ctx, events: Sequence[Event], perspective: str) -> str:
    cal = ctx.school.calendar
    parts = []
    for d, day in enumerate(cal.days):
        todays = sorted((e for e in events if e.day == d), key=lambda e: e.period)
        if todays:
            items = "".join(
                f'<li><span class="when"><b>{esc(cal.periods[e.period].label)}</b>'
                f"{esc(cal.periods[e.period].start)}</span>{_cell(ctx, e, perspective)}</li>"
                for e in todays
            )
            body = f"<ol>{items}</ol>"
        else:
            body = '<p class="none">No lessons.</p>'
        parts.append(f"<section><h3>{esc(day)}</h3>{body}</section>")
    return f'<div class="daylist">{"".join(parts)}</div>'


def legend(ctx: Ctx, subject_ids: Sequence[str]) -> str:
    items = "".join(
        f'<li><span class="swatch {ctx.sclass(sid)}"></span>{esc(ctx.school.subjects[sid].name)}</li>'
        for sid in subject_ids
    )
    return f'<ul class="legend" aria-label="Subject colours">{items}</ul>'


def _entity_page(
    ctx: Ctx,
    kind: str,
    entity_id: str,
    title: str,
    chips: list[str],
    events: list[Event],
    perspective: str,
    ics_href: str | None,
) -> str:
    sids = sorted({e.subject_id for e in events}, key=lambda s: ctx.subject_idx[s])
    chip_html = "".join(f"<li>{c}</li>" for c in chips)
    plural = {"class": "classes", "teacher": "teachers", "room": "rooms"}[kind]
    ics = (
        f'<a class="btn ghost no-print" href="../{ics_href}" download>Add to calendar (.ics)</a>'
        if ics_href
        else ""
    )
    body = f"""<p class="crumbs"><a href="../index.html#{plural}">&larr; All {plural}</a></p>
<h1>{esc(title)}</h1>
<ul class="chips">{chip_html}</ul>
<p class="no-print"><button type="button" onclick="window.print()">Print (A4 landscape)</button> {ics}</p>
{weekly_grid(ctx, events, perspective, f"Weekly timetable for {title}")}
{day_list(ctx, events, perspective)}
{legend(ctx, sids)}"""
    return body


def class_page(ctx: Ctx, cid: str, ics_href: str | None) -> tuple[str, str]:
    s = ctx.school
    k = s.classes[cid]
    events = ctx.tt.by_class(cid)
    lessons = sum(e.length for e in events)
    chips = [
        f"<b>{lessons}</b> lessons a week",
        f"<b>{k.size}</b> learners",
        f"Home room: <b>{esc(s.rooms[k.home_room].name)}</b>",
    ]
    body = _entity_page(ctx, "class", cid, k.name, chips, events, "class", ics_href)
    return k.name, body


def teacher_page(ctx: Ctx, tid: str, ics_href: str | None) -> tuple[str, str]:
    s = ctx.school
    t = s.teachers[tid]
    events = ctx.tt.by_teacher(tid)
    lessons = sum(e.length for e in events)
    days = len({e.day for e in events})
    subjects = ", ".join(sorted({s.subjects[e.subject_id].name for e in events}))
    chips = [
        f"<b>{lessons}</b> lessons a week (max {t.max_per_week})",
        f"<b>{days}</b> teaching day(s)",
        f"{esc(subjects)}" if subjects else "No lessons",
    ]
    body = _entity_page(
        ctx, "teacher", tid, f"{t.name} ({tid})", chips, events, "teacher", ics_href
    )
    return f"{t.name} ({tid})", body


def room_page(ctx: Ctx, rid: str, ics_href: str | None) -> tuple[str, str]:
    s = ctx.school
    r = s.rooms[rid]
    events = ctx.tt.by_room(rid)
    used = sum(e.length for e in events)
    total = len(s.calendar.slots)
    chips = [
        f"<b>{used}</b> of {total} periods booked",
        f"Type: <b>{esc(r.type)}</b>",
        f"Capacity <b>{r.capacity}</b>",
    ]
    body = _entity_page(ctx, "room", rid, r.name, chips, events, "room", ics_href)
    return r.name, body


# ----------------------------------------------------------------------- master grid
def master_page(ctx: Ctx, by: str) -> tuple[str, str]:
    school = ctx.school
    cal = school.calendar
    if by == "class":
        rows = [(cid, k.name, "classes", ctx.tt.by_class(cid)) for cid, k in school.classes.items()]
        labels = ("Subject", "Teacher", "Room")
        title = "Master grid by class"
    else:
        rows = [
            (
                tid,
                f"{t.name.split()[0][0]}. {t.name.split()[-1]} ({tid})",
                "teachers",
                ctx.tt.by_teacher(tid),
            )
            for tid, t in school.teachers.items()
            if ctx.tt.by_teacher(tid)
        ]
        labels = ("Class", "Subject", "Room")
        title = "Master grid by teacher"

    ncol = sum(cal.day_lengths)
    del ncol
    head1 = ['<th class="rowh" rowspan="2" scope="col">&nbsp;</th>']
    head2 = []
    for d, day in enumerate(cal.days):
        n = cal.day_lengths[d]
        head1.append(f'<th colspan="{n}" scope="colgroup" class="sepl dayend">{esc(day)}</th>')
        for p in range(n):
            cls = "sepl" if p == 0 else ""
            if p == n - 1:
                cls += " dayend"
            head2.append(f'<th scope="col" class="{cls}">{esc(cal.periods[p].label)}</th>')
    body_rows = []
    for ent_id, name, section, events in rows:
        start_at = {(e.day, e.period): e for e in events}
        covered = {(e.day, e.period + 1) for e in events if e.length == 2}
        cells = [
            f'<th scope="row" class="rowh"><a href="{section}/{esc(ent_id)}.html">{esc(name)}</a></th>'
        ]
        for d in range(len(cal.days)):
            for p in range(cal.day_lengths[d]):
                if (d, p) in covered:
                    continue
                cls = "sepl" if p == 0 else ""
                if p == cal.day_lengths[d] - 1 or (
                    (d, p) in start_at
                    and start_at[(d, p)].length == 2
                    and p + 1 == cal.day_lengths[d] - 1
                ):
                    cls += " dayend"
                if (d, p) in cal.blocked:
                    cells.append(f'<td class="{cls} blocked" title="No lessons">&times;</td>')
                    continue
                e = start_at.get((d, p))
                if e is None:
                    cells.append(f'<td class="{cls}"></td>')
                    continue
                span = f' colspan="{e.length}"' if e.length == 2 else ""
                cells.append(f'<td class="{cls}"{span}>{_master_cell(ctx, e, by)}</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    table = (
        '<div class="scroll"><table class="master view-1">'
        f'<caption class="sr-only">{esc(title)}</caption>'
        f"<thead><tr>{''.join(head1)}</tr><tr>{''.join(head2)}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></div>"
    )
    buttons = "".join(
        f'<button type="button" data-view="{i + 1}" aria-pressed="{"true" if i == 0 else "false"}">'
        f"{esc(lab)}</button>"
        for i, lab in enumerate(labels)
    )
    used = sorted({e.subject_id for e in ctx.tt.events}, key=lambda s: ctx.subject_idx[s])
    other = (
        '<a href="master-teachers.html">By teacher</a>'
        if by == "class"
        else '<a href="master.html">By class</a>'
    )
    body = f"""<h1>{esc(title)}</h1>
<p class="lede">Every lesson in the school on one sheet. Click a row name for the full page.</p>
<div class="master-tools no-print">
<div class="seg" id="view-tools" role="group" aria-label="What each cell shows">{buttons}</div>
<button type="button" onclick="window.print()">Print (A4 landscape)</button>
<span>Switch to: {other}</span>
</div>
{table}
{legend(ctx, used)}"""
    return title, body


def _master_cell(ctx: Ctx, e: Event, by: str) -> str:
    s = ctx.school
    sub = e.subject_id
    if by == "class":
        v1 = f"{esc(sub)}<small>{esc(e.teacher_id)}</small>"
        v2 = f"{esc(e.teacher_id)}<small>{esc(sub)}</small>"
        v3 = f"{esc(e.room_id)}<small>{esc(sub)}</small>"
    else:
        v1 = f"{esc(e.class_id)}<small>{esc(sub)}</small>"
        v2 = f"{esc(sub)}<small>{esc(e.class_id)}</small>"
        v3 = f"{esc(e.room_id)}<small>{esc(e.class_id)}</small>"
    label = (
        f"{s.calendar.label((e.day, e.period))}: {s.subjects[sub].name}, "
        f"{s.classes[e.class_id].name}, {s.teachers[e.teacher_id].name}, {s.rooms[e.room_id].name}"
    )
    return (
        f'<a class="{ctx.sclass(sub)}" href="#" onclick="return false" aria-label="{esc(label)}" '
        f'title="{esc(label)}"><span class="v1">{v1}</span><span class="v2">{v2}</span>'
        f'<span class="v3">{v3}</span></a>'
    )


# ----------------------------------------------------------------------------- index
def proof_panel(ctx: Ctx) -> str:
    rep = ctx.report
    ok = rep.ok
    rules = []
    for r in rep.rules:
        mark = "&#10003;" if r.ok else "&#10007;"
        cls = "" if r.ok else ' class="bad"'
        rules.append(
            f'<li{cls}><span class="mark" aria-hidden="true">{mark}</span>'
            f'<span><span class="sr-only">{"Passed" if r.ok else "Failed"}: </span>{esc(r.title)}</span>'
            f'<span class="n">{r.checked:,} checked</span></li>'
        )
    violations = ""
    if not ok:
        items = "".join(f"<li>{esc(v)}</li>" for v in rep.violations[:50])
        more = len(rep.violations) - 50
        extra = f"<li>and {more} more</li>" if more > 0 else ""
        violations = f'<ul class="violations">{items}{extra}</ul>'
    headline = (
        f'<span class="tick" aria-hidden="true">&#10003;</span> Clash-free: 0 violations in {rep.checks:,} checks'
        if ok
        else f'<span class="tick" aria-hidden="true">&#10007;</span> {len(rep.violations)} violation(s) found'
    )
    return f"""<section class="proof{"" if ok else " fail"}" id="proof" aria-labelledby="proof-h">
<h2 id="proof-h">{headline}</h2>
<p>Every hard rule was re-checked on the finished timetable by a separate validator that shares no code
with the solver. It reads only the lessons and the school's input.</p>
<ul class="rules">{"".join(rules)}</ul>
{violations}
<p class="footnote">This proves the timetable obeys the rules written in the input. It does not prove the
rules describe your school correctly; check the input files for that.</p>
</section>"""


def solve_panel(ctx: Ctx, breakdown: ScoreBreakdown, meta: dict[str, object]) -> str:
    rows = []
    biggest = max((i.penalty for i in breakdown.items), default=0) or 1
    for item in sorted(breakdown.items, key=lambda i: -i.penalty):
        width = round(160 * item.penalty / biggest)
        w = (
            f'<span class="bar" style="width:{width}px" aria-hidden="true"></span>'
            if item.penalty
            else ""
        )
        rows.append(
            f"<tr><td>{esc(item.label)}</td><td class=num>{item.count}</td>"
            f"<td class=num>{item.weight}</td><td class=num>{item.penalty}</td><td>{w}</td></tr>"
        )
    facts = []
    status = meta.get("status")
    if status:
        facts.append(f"Solver status: <b>{esc(status)}</b>")
    if meta.get("gap") is not None:
        facts.append(f"gap to best proven bound: <b>{float(str(meta['gap'])) * 100:.1f}%</b>")
    if meta.get("wall_time_s") is not None:
        facts.append(f"solve time: <b>{float(str(meta['wall_time_s'])):.1f} s</b>")
    if meta.get("machine"):
        facts.append(f"measured on {esc(meta['machine'])}")
    facts_html = ("<p>" + "; ".join(facts) + ".</p>") if facts else ""
    return f"""<section aria-labelledby="score-h">
<h2 id="score-h">How good is it? Soft-rule score</h2>
{facts_html}
<p>Hard rules can never be broken. Soft rules are preferences; each occurrence costs its weight and the
solver minimises the total. Lower is better; 0 would mean every preference is met.</p>
<div class="scroll"><table class="table">
<thead><tr><th>Soft rule</th><th class="num">Times</th><th class="num">Weight</th><th class="num">Penalty</th><th></th></tr></thead>
<tbody>{"".join(rows)}</tbody>
<tfoot><tr><th>Total penalty</th><th></th><th></th><th class="num">{breakdown.total}</th><th></th></tr></tfoot>
</table></div>
</section>"""


def finder_data(ctx: Ctx) -> dict[str, object]:
    s = ctx.school
    cal = s.calendar

    def table(entities: dict[str, list[Event]], other: str) -> dict[str, dict[str, dict[str, str]]]:
        out: dict[str, dict[str, dict[str, str]]] = {}
        for eid, events in entities.items():
            cells: dict[str, dict[str, str]] = {}
            for e in events:
                for d, p in e.slots:
                    cells[f"{d},{p}"] = {
                        "subject": s.subjects[e.subject_id].name,
                        "cls": s.classes[e.class_id].name,
                        "room": s.rooms[e.room_id].name,
                        "teacher": s.teachers[e.teacher_id].name,
                    }
            out[eid] = cells
        _ = other
        return out

    teachers_with = {t: ctx.tt.by_teacher(t) for t in s.teachers if ctx.tt.by_teacher(t)}
    return {
        "days": list(cal.days),
        "periods": [{"label": p.label, "start": p.start, "end": p.end} for p in cal.periods],
        "dayLengths": list(cal.day_lengths),
        "blocked": [f"{d},{p}" for d, p in sorted(cal.blocked)],
        "teachers": [{"id": t, "name": s.teachers[t].name} for t in teachers_with],
        "classes": [{"id": c, "name": k.name} for c, k in s.classes.items()],
        "byTeacher": table(teachers_with, "teacher"),
        "byClass": table({c: ctx.tt.by_class(c) for c in s.classes}, "class"),
    }


def index_page(
    ctx: Ctx, breakdown: ScoreBreakdown, meta: dict[str, object], has_ics: bool
) -> tuple[str, str]:
    s = ctx.school
    n_lessons = ctx.tt.lesson_count()
    sample = '<span class="badge">Synthetic sample data</span>' if s.synthetic else ""
    cards = "".join(
        f'<div class="card"><div class="stat">{n}</div><div class="stat-label">{label}</div></div>'
        for n, label in (
            (len(s.classes), "classes"),
            (len([t for t in s.teachers if ctx.tt.by_teacher(t)]), "teachers"),
            (len(s.rooms), "rooms"),
            (f"{n_lessons:,}", "lesson periods a week"),
        )
    )
    json_blob = json.dumps(finder_data(ctx), separators=(",", ":")).replace("</", "<\\/")
    finder = f"""<section aria-labelledby="find-h">
<h2 id="find-h">Where am I teaching?</h2>
<form id="finder" class="finder card" onsubmit="return false">
<div><label for="f-kind">Look up a</label><select id="f-kind"><option value="teacher">Teacher</option><option value="class">Class</option></select></div>
<div><label for="f-who">Who</label><select id="f-who"></select></div>
<div><label for="f-day">Day</label><select id="f-day"></select></div>
<div><label for="f-period">Period</label><select id="f-period"></select></div>
<div><button type="button" id="f-now">Right now</button></div>
</form>
<div class="answer" id="f-answer" role="status" aria-live="polite">Pick a teacher, day and period (needs JavaScript; the per-teacher pages below work without it).</div>
<script type="application/json" id="finder-data">{json_blob}</script>
</section>"""

    def listing(items: list[tuple[str, str, str]], anchor: str, heading: str, folder: str) -> str:
        lis = "".join(
            f'<li data-filter="{esc((name + " " + eid + " " + sub).lower())}">'
            f'<a href="{folder}/{esc(eid)}.html">{esc(name)}<small>{esc(sub)}</small></a></li>'
            for eid, name, sub in items
        )
        return f'<h2 id="{anchor}">{heading}</h2><ul class="dir">{lis}</ul>'

    classes = [
        (cid, k.name, f"{sum(e.length for e in ctx.tt.by_class(cid))} lessons")
        for cid, k in s.classes.items()
    ]
    teachers = []
    for tid, t in s.teachers.items():
        ev = ctx.tt.by_teacher(tid)
        if ev:
            subs = ", ".join(sorted({e.subject_id for e in ev}))
            teachers.append((tid, t.name, f"{tid} - {subs} - {sum(e.length for e in ev)} lessons"))
    used_rooms: Counter[str] = Counter()
    for e in ctx.tt.events:
        used_rooms[e.room_id] += e.length
    specialist = sorted(
        (rid for rid, r in s.rooms.items() if r.type in {x.room_type for x in s.subjects.values()}),
    )
    rooms = [
        (rid, s.rooms[rid].name, f"{s.rooms[rid].type} - {used_rooms.get(rid, 0)} periods")
        for rid in specialist
    ]
    bind = binding_constraints(s, ctx.tt)[:6]
    bind_html = ""
    if bind:
        items = "".join(f"<li>{esc(b.text)}</li>" for b in bind)
        bind_html = (
            '<section aria-labelledby="bind-h"><h2 id="bind-h">What limits this timetable</h2>'
            "<p>Resources that are close to full are the ones that shaped the result. "
            f"Fullest first.</p><ul>{items}</ul></section>"
        )
    exports = (
        '<section aria-labelledby="exp-h"><h2 id="exp-h">Exports</h2><ul>'
        '<li><a href="exports/timetable.csv" download>Whole timetable (CSV)</a>, one row per lesson</li>'
        + (
            "<li>Calendar files (.ics) for every teacher and class are on their pages, "
            "and in <code>exports/ics/</code>. Import into Google or Apple Calendar.</li>"
            if has_ics
            else ""
        )
        + "</ul></section>"
    )
    body = f"""<h1>{esc(s.name)} {sample}</h1>
<p class="lede">Weekly timetable for every class, teacher and room. Print any page on A4 landscape,
or open it on a phone to check a lesson.</p>
<div class="cards" role="list">{cards}</div>
<div style="height:var(--space-5)"></div>
{proof_panel(ctx)}
{finder}
{solve_panel(ctx, breakdown, meta)}
{bind_html}
<h2>Find a page</h2>
<div class="finder"><div><label for="dir-filter">Filter classes, teachers and rooms</label>
<input type="search" id="dir-filter" placeholder="e.g. chemistry, T07, 3N" autocomplete="off"></div></div>
{listing(classes, "classes", "Classes", "classes")}
{listing(teachers, "teachers", "Teachers", "teachers")}
{listing(rooms, "rooms", "Specialist rooms", "rooms")}
{exports}"""
    return "Timetable", body
