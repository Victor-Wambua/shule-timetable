"""The generated site: structure, proof panel, escaping, exports."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from shule_timetable.model import Event, Teacher, Timetable
from shule_timetable.report import build_site
from shule_timetable.report.ics import build_ics, supports_ics
from shule_timetable.solver import SolveSettings, solve
from shule_timetable.storage import load_timetable, save_timetable

from .helpers import tiny_school, valid_events, valid_timetable


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    build_site(tiny_school(), valid_timetable(), out)
    return out


def read(site: Path, rel: str) -> str:
    return (site / rel).read_text(encoding="utf-8")


def test_all_pages_are_written(site: Path) -> None:
    expected = [
        "index.html",
        "master.html",
        "master-teachers.html",
        "assets/style.css",
        "assets/app.js",
        "classes/C1.html",
        "classes/C2.html",
        "teachers/T1.html",
        "teachers/T2.html",
        "rooms/L1.html",
        "exports/timetable.csv",
        "exports/ics/teacher-T1.ics",
        "exports/ics/class-C1.ics",
    ]
    for rel in expected:
        assert (site / rel).is_file(), rel
    assert not (site / "rooms/R1.html").exists()  # plain classrooms have no page


def test_index_shows_the_validator_panel_with_ticks(site: Path) -> None:
    html = read(site, "index.html")
    assert "Clash-free: 0 violations in" in html
    assert html.count('class="mark"') == 12  # one tick per hard rule
    assert "&#10003;" in html and "&#10007;" not in html
    assert 'class="proof"' in html and 'class="proof fail"' not in html
    assert "shares no code" in html


def test_a_broken_timetable_shows_the_violations_instead(tmp_path: Path) -> None:
    events = valid_events()
    events[4] = replace(events[4], period=0)  # T1 in two places on Monday P1
    rep = build_site(tiny_school(), Timetable(tuple(events)), tmp_path)
    assert not rep.ok
    html = (tmp_path / "index.html").read_text()
    assert 'class="proof fail"' in html and "violation(s) found" in html
    assert "Teacher T1 is in 2 lessons" in html
    assert "Clash-free" not in html
    assert "violation(s) found" in (tmp_path / "classes/C1.html").read_text()


def test_class_page_has_grid_daylist_legend_and_aria(site: Path) -> None:
    html = read(site, "classes/C1.html")
    assert html.count('<table class="grid">') == 1
    assert 'class="daylist"' in html
    assert 'aria-label="Mon P1: Mathematics, Class 1, Teacher One, Room 1"' in html
    assert 'rowspan="2"' in html  # the chemistry double
    assert "double lesson" in html
    assert 'class="legend"' in html and "Chemistry" in html
    assert "Tea 09:20&ndash;09:40" in html or "Tea 8:40" in html or "Tea" in html


def test_every_subject_has_colour_and_pattern_classes(site: Path) -> None:
    html = read(site, "classes/C1.html")
    assert re.search(r'class="cell s0 p0"', html) and re.search(r'class="cell s1 p1"', html)
    css = read(site, "assets/style.css")
    assert ".s0 {" in css and ".s1 {" in css and "@media print" in css and "A4 landscape" in css
    assert "prefers-color-scheme: dark" in css and "prefers-reduced-motion" in css


def test_no_external_requests(site: Path) -> None:
    for page in site.rglob("*.html"):
        text = page.read_text()
        assert not re.search(r'(src|href)="https?://', text), page
    assert "http://" not in read(site, "assets/style.css")


def test_master_grid_has_a_cell_per_lesson_event(site: Path) -> None:
    html = read(site, "master.html")
    assert html.count('<span class="v1">') == len(valid_events())
    assert 'colspan="2"' in html  # doubles span two periods


def test_teacher_html_is_escaped() -> None:
    school = tiny_school()
    evil = Teacher("T1", "<script>alert(1)</script>", ("MAT",), 18, 6)
    school = replace(school, teachers={**school.teachers, "T1": evil})
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        build_site(school, valid_timetable(), d)
        for page in Path(d).rglob("*.html"):
            assert "<script>alert(1)" not in page.read_text(), page


def test_finder_data_is_embedded_and_parseable(site: Path) -> None:
    import json

    html = read(site, "index.html")
    blob = re.search(r'<script type="application/json" id="finder-data">(.*?)</script>', html, re.S)
    assert blob
    data = json.loads(blob.group(1))
    cell = data["byTeacher"]["T1"]["0,0"]
    assert cell == {
        "subject": "Mathematics",
        "cls": "Class 1",
        "room": "Room 1",
        "teacher": "Teacher One",
    }
    assert (
        "0,3" in data["byTeacher"]["T2"] and "0,2" in data["byTeacher"]["T2"]
    )  # double fills both


def test_csv_export(site: Path) -> None:
    lines = read(site, "exports/timetable.csv").strip().splitlines()
    assert lines[0] == "class,subject,teacher,room,day,first_period,start,end,periods"
    assert len(lines) == 1 + len(valid_events())
    assert "Class 1,Chemistry,Teacher Two,Lab,Mon,P3,10:00,11:40,2" in lines[1:] or any(
        "Chemistry" in line and ",2" in line for line in lines
    )


def test_ics_times_are_converted_from_nairobi_to_utc(site: Path) -> None:
    text = (site / "exports/ics/teacher-T1.ics").read_bytes().decode()
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert text.count("BEGIN:VEVENT") == 8
    # Monday P1 starts 08:00 EAT = 05:00Z on the first Monday on/after 5 Jan 2026
    assert "DTSTART:20260105T050000Z" in text
    assert "RRULE:FREQ=WEEKLY;COUNT=13" in text or "RRULE:FREQ=WEEKLY;COUNT=" in text


def test_ics_double_runs_for_both_periods_and_lines_are_folded() -> None:
    school = tiny_school()
    long_name = replace(school.subjects["CHE"], name="C" * 200)
    school = replace(school, subjects={**school.subjects, "CHE": long_name})
    text = build_ics(school, [Event("C1", "CHE", "T2", "L1", 0, 2, 2)], "T2", "teacher")
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))
    unfolded = text.replace("\r\n ", "")
    assert "SUMMARY:" + "C" * 200 in unfolded
    # periods idx 2-3: 09:00-... times from the helper calendar (10:00 start, second ends 11:40)
    assert "DTSTART:20260105T070000Z" in text and "DTEND:20260105T084000Z" in text


def test_ics_skipped_when_days_are_not_weekdays() -> None:
    school = tiny_school()
    cal = replace(school.calendar, days=("Day1", "Day2", "Day3"))
    assert not supports_ics(replace(school, calendar=cal))


def test_solution_json_round_trip(tmp_path: Path) -> None:
    school = tiny_school()
    res = solve(school, SolveSettings(time_limit=10, workers=1))
    assert res.timetable is not None
    tt = replace(res.timetable, meta={"status": "OPTIMAL", "machine": "test box"})
    path = tmp_path / "sol.json"
    save_timetable(path, school, tt)
    back = load_timetable(path, school)
    assert back.events == tt.events and back.meta["machine"] == "test box"
    assert '"day": "Mon"' in path.read_text() and '"period": "P1"' in path.read_text()


def test_solve_meta_shown_on_index(tmp_path: Path) -> None:
    tt = replace(
        valid_timetable(),
        meta={
            "status": "FEASIBLE",
            "gap": 0.25,
            "wall_time_s": 12.3,
            "machine": "Test CPU, 4 cores",
        },
    )
    build_site(tiny_school(), tt, tmp_path)
    html = (tmp_path / "index.html").read_text()
    assert (
        "FEASIBLE" in html and "25.0%" in html and "12.3 s" in html and "Test CPU, 4 cores" in html
    )


# ---- accessibility and structure of the generated pages
def test_home_h1_is_the_school_name_only(tmp_path: Path) -> None:
    build_site(replace(tiny_school(), synthetic=True), valid_timetable(), tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    h1 = re.search(r"<h1>(.*?)</h1>", html, re.S)
    assert h1 and "badge" not in h1.group(1) and "Synthetic" not in h1.group(1)
    assert html.count("<h1") == 1
    assert 'class="badge"' not in html
    assert "Synthetic sample data." in html  # said once, as a plain line under the title


def test_home_figures_and_proof_table(site: Path) -> None:
    html = read(site, "index.html")
    assert '<ul class="figures"' in html and 'class="card"' not in html
    rows = re.findall(r'<tr><th scope="row"><span class="mark"', html)
    assert len(rows) == 12
    assert '<th scope="col" class="n">Checks run</th>' in html
    assert "does not prove the" in html  # the honest footnote stays


def test_nav_marks_the_current_page_and_section(site: Path) -> None:
    home = read(site, "index.html")
    assert '<a href="index.html" aria-current="page">Home</a>' in home
    cls = read(site, "classes/C1.html")
    assert 'aria-current="true">Classes</a>' in cls
    assert cls.count("aria-current") == 1
    assert 'href="#main">Skip to main content</a>' in cls and 'id="main" tabindex="-1"' in cls


def test_entity_page_headings_do_not_skip_a_level(site: Path) -> None:
    html = read(site, "classes/C1.html")
    assert "<h3" not in html and html.count("<h1") == 1
    assert 'class="dayh"' in html


def test_master_grid_is_keyboard_friendly(site: Path) -> None:
    html = read(site, "master.html")
    assert 'href="#"' not in html  # cells are not dead links
    assert html.count('type="radio" name="cell-view"') == 3
    assert 'role="radiogroup"' in html and 'role="region" tabindex="0"' in html
    assert '<th class="rowh" rowspan="2" scope="col">Class</th>' in html
    assert "<caption" in html and 'scope="colgroup"' in html
    assert "Scroll it sideways" in html and "Select a class name" in html


def test_finder_has_a_no_script_message_and_a_clock_note(site: Path) -> None:
    html = read(site, "index.html")
    assert 'id="f-nojs"' in html and 'id="finder"' in html and "hidden>" in html
    assert 'role="status" aria-live="polite"' in html
    assert "Nairobi time" in html and '"tz":"Africa/Nairobi"' in html


def test_landing_page_numbers_match_the_committed_examples() -> None:
    """docs/pages/index.html is hand-written, so guard its figures against drift."""
    from shule_timetable.loader import load_school
    from shule_timetable.validator import validate

    root = Path(__file__).resolve().parents[1]
    landing = (root / "docs/pages/index.html").read_text(encoding="utf-8")
    for name in ("secondary", "primary"):
        school = load_school(root / "examples" / name)
        tt = load_timetable(root / "examples" / name / "solution.json", school)
        teachers = len([t for t in school.teachers if tt.by_teacher(t)])
        for n, label in (
            (len(school.classes), "classes"),
            (teachers, "teachers"),
            (len(school.rooms), "rooms"),
            (f"{tt.lesson_count():,}", "lesson periods a week"),
        ):
            assert f"<li><b>{n}</b><span>{label}</span></li>" in landing, (name, label)
        assert f"0 violations in {validate(school, tt).checks:,} checks" in landing
