"""End-to-end through the command line, plus the sample-data generators."""

from __future__ import annotations

from pathlib import Path

import pytest

from shule_timetable.cli import main
from shule_timetable.demo import generate, generate_primary, generate_secondary, write_inputs
from shule_timetable.loader import load_school
from shule_timetable.prechecks import run_prechecks

from .helpers import TINY_FILES

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tiny(tmp_path: Path) -> Path:
    write_inputs(TINY_FILES, tmp_path / "in")
    return tmp_path / "in"


def run(*argv: str) -> int:
    with pytest.raises(SystemExit) as exc:
        main(list(argv))
    code = exc.value.code
    assert isinstance(code, int)
    return code


def test_validate_ok(tiny: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("validate", str(tiny)) == 0
    out = capsys.readouterr().out
    assert "2 classes, 2 teachers, 3 rooms, 14 lessons a week into 18 slots" in out


def test_validate_reports_all_errors_with_pointers(
    tiny: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tiny / "requirements.csv").write_text(
        "class,subject,teacher,lessons,doubles\nC9,MAT,T1,4,0\nC1,MAT,T7,4,0\n"
    )
    assert run("validate", str(tiny)) == 1
    err = capsys.readouterr().err
    assert "requirements.csv:2" in err and "class 'C9'" in err
    assert "requirements.csv:3" in err and "teacher 'T7'" in err
    assert "2 error(s)" in err


def test_validate_explains_an_impossible_input(
    tiny: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tiny / "teachers.csv").write_text(
        "id,name,subjects,max_per_week,max_per_day,unavailable\n"
        "T1,Teacher One,MAT,5,6,\nT2,Teacher Two,CHE,18,6,\n"
    )
    assert run("validate", str(tiny)) == 1
    assert (
        "Teacher T1 (Teacher One) is assigned 8 lessons/week but max_per_week is 5"
        in capsys.readouterr().err
    )


def test_solve_report_and_validate_solution(
    tiny: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sol = tmp_path / "solution.json"
    assert run("solve", str(tiny), "-o", str(sol), "--time-limit", "10", "--workers", "1") == 0
    out = capsys.readouterr().out
    assert "Status OPTIMAL" in out and "Independent validator" in out and "FAIL" not in out
    assert run("validate", str(tiny), "--solution", str(sol)) == 0
    site = tmp_path / "site"
    assert run("report", str(tiny), "--solution", str(sol), "--out", str(site)) == 0
    assert (site / "index.html").exists() and (site / "teachers/T1.html").exists()


def test_explain_on_feasible_input(tiny: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("explain", str(tiny), "--time-limit", "10", "--workers", "1") == 0
    assert "A timetable exists" in capsys.readouterr().out


def test_explain_on_infeasible_input_prints_the_conflict(
    tiny: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tiny / "teachers.csv").write_text(
        "id,name,subjects,max_per_week,max_per_day,unavailable\n"
        "T1,Teacher One,MAT,18,6,\nT2,Teacher Two,CHE,18,6,Mon:P1-P4;Tue:*;Wed:*\n"
    )
    assert run("explain", str(tiny), "--time-limit", "10") == 2
    out = capsys.readouterr().out
    assert "No timetable exists" in out and "Teacher T2" in out


def test_repair_from_the_command_line(
    tiny: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sol = tmp_path / "solution.json"
    assert run("solve", str(tiny), "-o", str(sol), "--time-limit", "10", "--workers", "1") == 0
    change = tmp_path / "change.yaml"
    change.write_text("changes:\n  - unavailable: {teacher: T1, slots: 'Mon:*'}\n")
    new = tmp_path / "repaired.json"
    capsys.readouterr()
    code = run(
        "repair",
        str(tiny),
        "--solution",
        str(sol),
        "--change",
        str(change),
        "-o",
        str(new),
        "--compare-scratch",
        "--time-limit",
        "10",
        "--workers",
        "1",
    )
    out = capsys.readouterr().out
    assert code == 0 and new.exists()
    assert "Teacher T1 becomes unavailable Mon:*" in out
    assert "re-solving from scratch moves" in out and "OK   No teacher is in two places" in out


def test_demo_command_on_primary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "demo"
    assert (
        run("demo", "--school", "primary", "--out", str(out), "--time-limit", "5", "--workers", "1")
        == 0
    )
    text = capsys.readouterr().out
    assert "6 classes, 8 teachers" in text and "Solved: status" in text
    assert (out / "site/index.html").exists() and (out / "solution.json").exists()


# ---- generators and the committed examples ------------------------------------------------
@pytest.mark.parametrize("streams", [1, 2, 3, 4, 5, 6])
def test_secondary_generator_scales_and_passes_prechecks(streams: int, tmp_path: Path) -> None:
    write_inputs(generate_secondary(streams=streams), tmp_path)
    school = load_school(tmp_path)
    assert len(school.classes) == 4 * streams
    assert [i for i in run_prechecks(school) if i.severity == "error"] == []


def test_default_secondary_matches_the_brief(tmp_path: Path) -> None:
    write_inputs(generate_secondary(), tmp_path)
    school = load_school(tmp_path)
    assert len(school.classes) == 16
    assert 26 <= len(school.teachers) <= 34
    assert len([r for r in school.rooms.values() if r.type.endswith("_lab")]) >= 4


def test_generators_are_deterministic() -> None:
    assert generate_secondary() == generate_secondary()
    assert generate_primary() == generate_primary()


@pytest.mark.parametrize("kind", ["secondary", "primary"])
def test_committed_examples_match_the_generator(kind: str) -> None:
    for name, text in generate(kind).items():
        assert (ROOT / "examples" / kind / name).read_text() == text, (
            f"{kind}/{name} is stale: run make examples"
        )


def test_unknown_sample_school() -> None:
    with pytest.raises(ValueError, match="unknown sample school"):
        generate("university")
