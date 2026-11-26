"""Input parsing: the happy path, and a clear pointer for every kind of mistake."""

from __future__ import annotations

from pathlib import Path

import pytest

from shule_timetable.demo import generate_primary, write_inputs
from shule_timetable.issues import InputError
from shule_timetable.loader import load_school, load_with_issues


@pytest.fixture
def inputs(tmp_path: Path) -> Path:
    write_inputs(generate_primary(), tmp_path)
    return tmp_path


def edit(path: Path, name: str, old: str, new: str) -> None:
    f = path / name
    text = f.read_text()
    assert old in text, f"{old!r} not in {name}"
    f.write_text(text.replace(old, new, 1))


def errors(path: Path) -> list[str]:
    school, issues = load_with_issues(path)
    assert school is None
    return [str(i) for i in issues if i.severity == "error"]


def test_sample_loads(inputs: Path) -> None:
    school = load_school(inputs)
    assert len(school.classes) == 6
    assert len(school.teachers) == 8
    assert school.synthetic
    assert school.calendar.day_lengths == (7, 7, 7, 7, 5)
    assert (0, 0) in school.calendar.blocked
    assert school.term is not None and school.term.weeks == 13


def test_missing_directory() -> None:
    school, issues = load_with_issues("/nonexistent/dir")
    assert school is None and "not a directory" in issues[0].message


def test_missing_file(inputs: Path) -> None:
    (inputs / "rooms.csv").unlink()
    assert any("rooms.csv not found" in e for e in errors(inputs))


def test_missing_column(inputs: Path) -> None:
    edit(inputs, "teachers.csv", "max_per_week", "weekly")
    assert any("missing column(s) max_per_week" in e for e in errors(inputs))


def test_unknown_class_with_suggestion_and_line_number(inputs: Path) -> None:
    edit(inputs, "requirements.csv", "G3,ENG", "G33,ENG")
    msgs = errors(inputs)
    assert any(
        "requirements.csv:" in m and "class 'G33'" in m and "Did you mean 'G3'" in m for m in msgs
    )


def test_unknown_subject_in_teacher_list(inputs: Path) -> None:
    edit(inputs, "teachers.csv", "PE", "PEE")
    assert any("lists subject 'PEE'" in e and "teachers.csv:" in e for e in errors(inputs))


def test_bad_number(inputs: Path) -> None:
    edit(inputs, "teachers.csv", ",28,6,", ",lots,6,")
    assert any("max_per_week must be a whole number, got 'lots'" in e for e in errors(inputs))


def test_teacher_not_qualified_for_assigned_subject(inputs: Path) -> None:
    edit(inputs, "requirements.csv", "G1,PE,T07", "G1,PE,T01")
    msgs = errors(inputs)
    assert any("Teacher T01" in e and "does not include PE" in e for e in msgs)


def test_duplicate_ids_and_requirements(inputs: Path) -> None:
    text = (inputs / "classes.csv").read_text()
    (inputs / "classes.csv").write_text(text + "G1,Grade 1 again,30,R01\n")
    assert any("class id 'G1' appears twice" in e for e in errors(inputs))


def test_two_classes_sharing_a_home_room(inputs: Path) -> None:
    edit(inputs, "classes.csv", "R02", "R01")
    assert any("both use home room 'R01'" in e for e in errors(inputs))


def test_too_many_doubles(inputs: Path) -> None:
    edit(inputs, "requirements.csv", "G1,SCI,T01,3,1", "G1,SCI,T01,3,2")
    assert any("need 4 periods but only 3 lessons" in e for e in errors(inputs))


def test_class_too_big_for_every_specialist_room(inputs: Path) -> None:
    edit(
        inputs,
        "rooms.csv",
        "SCI1,Science Room,science_room,45",
        "SCI1,Science Room,science_room,10",
    )
    assert any("largest 'science_room' room holds 10" in e for e in errors(inputs))


def test_no_room_of_required_type(inputs: Path) -> None:
    edit(inputs, "rooms.csv", "FLD1,School Field,field,200\n", "")
    assert any("needs a 'field' room but rooms.csv has none" in e for e in errors(inputs))


def test_bad_period_label_in_unavailable(inputs: Path) -> None:
    edit(inputs, "teachers.csv", "Thu:*", "Thu:P99")
    assert any("unavailable: unknown period 'P99'" in e for e in errors(inputs))


def test_bad_time_in_yaml(inputs: Path) -> None:
    edit(inputs, "school.yaml", '"08:00"', '"8am"')
    assert any("periods[0].start must be HH:MM, got '8am'" in e for e in errors(inputs))


def test_broken_yaml(inputs: Path) -> None:
    (inputs / "school.yaml").write_text("days: [Mon\nperiods: {")
    assert any("could not parse YAML" in e and "school.yaml" in e for e in errors(inputs))


def test_unknown_weight_name_gets_a_suggestion(inputs: Path) -> None:
    edit(inputs, "school.yaml", "teacher_gaps: 2", "teacher_gapss: 2")
    assert any(
        "unknown weight 'teacher_gapss'" in e and "Did you mean 'teacher_gaps'" in e
        for e in errors(inputs)
    )


def test_all_errors_are_reported_together(inputs: Path) -> None:
    edit(inputs, "requirements.csv", "G3,ENG", "G33,ENG")
    edit(inputs, "teachers.csv", "PE", "PEE")
    assert len(errors(inputs)) >= 2


def test_teacher_subject_nobody_needs_is_a_warning(inputs: Path) -> None:
    edit(inputs, "teachers.csv", "ART;AGR", "ART;AGR;SST")
    # SST is needed by classes, so use a subject no class needs
    edit(inputs, "subjects.csv", "PE,", "MUS,Music,home,all,0,no,no\nPE,")
    edit(inputs, "teachers.csv", "ART;AGR;SST", "ART;AGR;MUS")
    school, issues = load_with_issues(inputs)
    assert school is not None
    assert any("teaches Music but no class needs Music" in i.message for i in issues)


def test_load_school_raises_with_all_messages(inputs: Path) -> None:
    edit(inputs, "requirements.csv", "G3,ENG", "G33,ENG")
    with pytest.raises(InputError) as exc:
        load_school(inputs)
    assert "G33" in str(exc.value)
