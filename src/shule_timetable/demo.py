"""Synthetic sample schools.

Everything here is invented: school names, teacher names, class sizes and the weekly lesson
counts. The generator is deterministic (fixed seed), so the committed ``examples/`` folders
can be rebuilt byte-for-byte with ``make examples``.

The lesson counts are plausible for a Kenyan secondary or primary timetable, not an
official curriculum: supply your own in ``requirements.csv``.
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

STREAMS = ["N", "E", "W", "S", "C", "H"]
FIRST = [
    "Achieng",
    "Wanjiru",
    "Kamau",
    "Otieno",
    "Njeri",
    "Mutiso",
    "Chebet",
    "Odhiambo",
    "Wafula",
    "Naliaka",
    "Kiprop",
    "Atieno",
    "Mwangi",
    "Akinyi",
    "Barasa",
    "Wairimu",
    "Kipchoge",
    "Nyambura",
    "Mumbua",
    "Omondi",
    "Cherono",
    "Karanja",
    "Adhiambo",
    "Simiyu",
    "Wangari",
    "Kilonzo",
    "Jepkosgei",
    "Maina",
    "Anyango",
    "Ndungu",
    "Auma",
    "Kariuki",
    "Naserian",
    "Mutua",
]
LAST = [
    "Mwangi",
    "Otieno",
    "Kamau",
    "Wekesa",
    "Njoroge",
    "Muthoni",
    "Kiplagat",
    "Onyango",
    "Waweru",
    "Musyoka",
    "Rotich",
    "Ouma",
    "Gitau",
    "Chelimo",
    "Nyongesa",
    "Mbugua",
    "Koech",
    "Ndegwa",
    "Wambui",
    "Juma",
    "Kimani",
    "Opiyo",
    "Njuguna",
    "Lagat",
    "Makau",
    "Wanyama",
    "Cheruiyot",
]

SECONDARY_SUBJECTS = [
    # id, name, room_type, room_use, doubles, heavy, avoid_edges
    ("ENG", "English", "home", "all", 0, True, False),
    ("KIS", "Kiswahili", "home", "all", 0, False, False),
    ("MAT", "Mathematics", "home", "all", 0, True, False),
    ("BIO", "Biology", "bio_lab", "doubles", 1, False, False),
    ("CHE", "Chemistry", "chem_lab", "doubles", 1, True, False),
    ("PHY", "Physics", "phy_lab", "doubles", 1, True, False),
    ("HIS", "History and Government", "home", "all", 0, False, False),
    ("GEO", "Geography", "home", "all", 0, False, False),
    ("CRE", "Christian Religious Education", "home", "all", 0, False, False),
    ("BST", "Business Studies", "home", "all", 0, False, False),
    ("AGR", "Agriculture", "home", "all", 0, False, False),
    ("CMP", "Computer Studies", "computer_lab", "all", 1, False, False),
    ("PE", "Physical Education", "field", "all", 0, False, True),
]

JUNIOR = {  # Forms 1 and 2: the same for every stream
    "ENG": 5,
    "KIS": 4,
    "MAT": 5,
    "BIO": 3,
    "CHE": 3,
    "PHY": 3,
    "HIS": 2,
    "GEO": 3,
    "CRE": 2,
    "BST": 2,
    "CMP": 2,
    "PE": 2,
}
SENIOR = [  # Forms 3 and 4: subject clusters, rotated across streams
    {"ENG": 5, "KIS": 4, "MAT": 5, "CHE": 4, "BIO": 4, "GEO": 4, "BST": 4, "CRE": 2, "PE": 1},
    {
        "ENG": 5,
        "KIS": 4,
        "MAT": 5,
        "CHE": 4,
        "PHY": 4,
        "HIS": 3,
        "AGR": 4,
        "CRE": 2,
        "CMP": 2,
        "PE": 1,
    },
    {
        "ENG": 5,
        "KIS": 4,
        "MAT": 5,
        "CHE": 4,
        "BIO": 4,
        "HIS": 3,
        "CMP": 4,
        "CRE": 2,
        "GEO": 2,
        "PE": 1,
    },
    {"ENG": 5, "KIS": 4, "MAT": 5, "CHE": 4, "PHY": 4, "GEO": 4, "BST": 4, "CRE": 2, "PE": 1},
]
POOLS = [
    ["ENG"],
    ["KIS"],
    ["MAT", "CMP"],
    ["BIO", "AGR"],
    ["CHE"],
    ["PHY"],
    ["HIS", "CRE"],
    ["GEO", "BST"],
    ["PE"],
]

SCHOOL_YAML_SECONDARY = """\
# Shule Timetable input. SYNTHETIC sample: the school, people and lesson counts are invented.
name: Mwangaza Hills Secondary School (synthetic sample)
synthetic: true
term: {{start: 2026-01-05, weeks: 13}}

days: [Mon, Tue, Wed, Thu, Fri]
periods:
  - {{label: P1, start: "08:00", end: "08:40"}}
  - {{label: P2, start: "08:40", end: "09:20"}}
  - {{label: P3, start: "09:40", end: "10:20"}}
  - {{label: P4, start: "10:20", end: "11:00"}}
  - {{label: P5, start: "11:20", end: "12:00"}}
  - {{label: P6, start: "12:00", end: "12:40"}}
  - {{label: P7, start: "13:30", end: "14:10"}}
  - {{label: P8, start: "14:10", end: "14:50"}}
breaks:                       # a break sits after the named period; doubles cannot span it
  - {{after: P2, name: Tea}}
  - {{after: P4, name: Break}}
  - {{after: P6, name: Lunch, long: true}}   # long = ends a "stretch" of back-to-back teaching
short_days: {{Fri: 6}}          # Friday has lessons in P1-P6 only

limits:
  max_per_subject_per_day: 2
  max_consecutive_lessons: 3   # more than this back to back counts against the timetable
  morning_until: P4

light_slots: ["Fri:P5-P6"]    # keep Friday late morning light (soft)

weights:                       # penalty per occurrence; 0 switches a soft rule off
  spread_subjects: 4
  teacher_consecutive: 6
  teacher_gaps: 2
  class_gaps: 8
  heavy_morning: 3
  balance_daily_load: 2
  avoid_edges: 3
  teacher_days_compact: 1
  light_slots: 2
"""

SCHOOL_YAML_PRIMARY = """\
# Shule Timetable input. SYNTHETIC sample: the school, people and lesson counts are invented.
name: Jitahidi Primary School (synthetic sample)
synthetic: true
term: {start: 2026-01-05, weeks: 13}

days: [Mon, Tue, Wed, Thu, Fri]
periods:
  - {label: P1, start: "08:00", end: "08:35"}
  - {label: P2, start: "08:35", end: "09:10"}
  - {label: P3, start: "09:30", end: "10:05"}
  - {label: P4, start: "10:05", end: "10:40"}
  - {label: P5, start: "10:40", end: "11:15"}
  - {label: P6, start: "12:05", end: "12:40"}
  - {label: P7, start: "12:40", end: "13:15"}
breaks:
  - {after: P2, name: Tea}
  - {after: P5, name: Lunch, long: true}
short_days: {Fri: 5}
blocked: ["Mon:P1"]            # flag-raising assembly

limits:
  max_per_subject_per_day: 2
  max_consecutive_lessons: 3
  morning_until: P5

weights:
  spread_subjects: 4
  teacher_consecutive: 6
  teacher_gaps: 2
  class_gaps: 8
  heavy_morning: 3
  balance_daily_load: 2
  avoid_edges: 3
  teacher_days_compact: 1
  light_slots: 2
"""


def _csv(header: list[str], rows: list[list[object]]) -> str:
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    return "\n".join(lines) + "\n"


def _yn(flag: bool) -> str:
    return "yes" if flag else "no"


def _names(rng: random.Random, n: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    while len(out) < n:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def generate_secondary(streams: int = 4, seed: int = 7) -> dict[str, str]:
    """A secondary school with ``4 * streams`` classes (16 by default)."""
    rng = random.Random(seed)
    names = STREAMS[:streams]
    classes: list[tuple[str, str, int, str]] = []
    needs: list[tuple[str, str, int]] = []  # class, subject, lessons
    for form in (1, 2, 3, 4):
        for si, stream in enumerate(names):
            cid = f"{form}{stream}"
            room = f"R{len(classes) + 1:02d}"
            classes.append((cid, f"Form {form}{stream}", rng.randint(38, 44), room))
            plan = JUNIOR if form <= 2 else SENIOR[(si + form) % len(SENIOR)]
            for sid, n in plan.items():
                needs.append((cid, sid, n))

    subject_row = {s[0]: s for s in SECONDARY_SUBJECTS}
    teachers: list[dict[str, object]] = []
    reqs: list[tuple[str, str, str, int, int]] = []
    for pool in POOLS:
        items = sorted((n for n in needs if n[1] in pool), key=lambda n: (-n[2], n[0], n[1]))
        total = sum(n[2] for n in items)
        count = max(1, math.ceil(total / 22))
        loads = [0] * count
        taught: list[set[str]] = [set() for _ in range(count)]
        first_idx = len(teachers)
        for cid, sid, n in items:
            i = min(range(count), key=lambda j: (loads[j], j))
            loads[i] += n
            taught[i].add(sid)
            doubles = int(subject_row[sid][4])
            reqs.append((cid, sid, f"T{first_idx + i + 1:02d}", n, doubles))
        for i in range(count):
            teachers.append({"subjects": sorted(taught[i]), "load": loads[i]})

    # number the teachers in pool order and give a few of them realistic constraints
    tnames = _names(rng, len(teachers))
    light = [i for i, t in enumerate(teachers) if int(str(t["load"])) <= 22]
    rng.shuffle(light)
    unavail_options = ["Wed:*", "Fri:P5-P6", "Mon:P1-P2", "Thu:P7-P8"]
    unavailable: dict[int, str] = {}
    for idx, spec in zip(light[: len(unavail_options)], unavail_options, strict=False):
        unavailable[idx] = spec
    if teachers:
        # a deputy head who carries a reduced timetable
        deputy = min(range(len(teachers)), key=lambda i: int(str(teachers[i]["load"])))
        teachers[deputy]["cap"] = max(int(str(teachers[deputy]["load"])), 14)
    teacher_rows = []
    for i, t in enumerate(teachers):
        cap = int(str(t.get("cap", 28)))
        teacher_rows.append(
            [
                f"T{i + 1:02d}",
                tnames[i],
                ";".join(str(s) for s in t["subjects"]),
                cap,
                6,
                unavailable.get(i, ""),
            ]
        )

    n_class = len(classes)
    rooms: list[list[object]] = [[c[3], f"Classroom {c[3][1:]}", "classroom", 45] for c in classes]
    rooms += [
        ["CH1", "Chemistry Lab 1", "chem_lab", 45],
        ["CH2", "Chemistry Lab 2", "chem_lab", 45],
    ]
    rooms += [["BL1", "Biology Lab", "bio_lab", 45], ["PL1", "Physics Lab", "phy_lab", 45]]
    rooms += [["CL1", "Computer Lab", "computer_lab", 45]]
    rooms += [["FLD1", "Main Field", "field", 200], ["FLD2", "Upper Field", "field", 200]]
    if n_class > 24:
        rooms += [["CH3", "Chemistry Lab 3", "chem_lab", 45]]

    return {
        "school.yaml": SCHOOL_YAML_SECONDARY.format(),
        "subjects.csv": _csv(
            ["id", "name", "room_type", "room_use", "doubles", "heavy", "avoid_edges"],
            [
                [s[0], s[1], s[2], s[3], s[4], _yn(bool(s[5])), _yn(bool(s[6]))]
                for s in SECONDARY_SUBJECTS
            ],
        ),
        "rooms.csv": _csv(["id", "name", "type", "capacity"], rooms),
        "classes.csv": _csv(["id", "name", "size", "home_room"], [list(c) for c in classes]),
        "teachers.csv": _csv(
            ["id", "name", "subjects", "max_per_week", "max_per_day", "unavailable"], teacher_rows
        ),
        "requirements.csv": _csv(
            ["class", "subject", "teacher", "lessons", "doubles"], [list(r) for r in reqs]
        ),
    }


PRIMARY_SUBJECTS = [
    ("ENG", "English", "home", "all", 0, True, False),
    ("KIS", "Kiswahili", "home", "all", 0, False, False),
    ("MAT", "Mathematics", "home", "all", 0, True, False),
    ("SCI", "Science and Technology", "science_room", "doubles", 1, False, False),
    ("SST", "Social Studies", "home", "all", 0, False, False),
    ("CRE", "Christian Religious Education", "home", "all", 0, False, False),
    ("ART", "Creative Arts", "home", "all", 1, False, False),
    ("AGR", "Agriculture and Nutrition", "home", "all", 0, False, False),
    ("PE", "Physical Education", "field", "all", 0, False, True),
]
PRIMARY_PLAN = {
    "ENG": 5,
    "KIS": 4,
    "MAT": 5,
    "SCI": 3,
    "SST": 3,
    "CRE": 2,
    "ART": 2,
    "AGR": 2,
    "PE": 3,
}


def generate_primary(seed: int = 11) -> dict[str, str]:
    """A small primary school: six classes, eight teachers, class teachers plus two specialists."""
    rng = random.Random(seed)
    names = _names(rng, 8)
    classes = [(f"G{g}", f"Grade {g}", rng.randint(32, 40), f"R{g:02d}") for g in range(1, 7)]
    teachers = []
    reqs: list[list[object]] = []
    class_teacher_subjects = ["ENG", "KIS", "MAT", "SCI", "SST", "CRE"]
    for i, (cid, _n, _s, _r) in enumerate(classes):
        tid = f"T{i + 1:02d}"
        for sid in class_teacher_subjects:
            reqs.append([cid, sid, tid, PRIMARY_PLAN[sid], 1 if sid == "SCI" else 0])
        teachers.append([tid, names[i], ";".join(class_teacher_subjects), 28, 6, ""])
    for cid, *_ in classes:
        reqs.append([cid, "PE", "T07", PRIMARY_PLAN["PE"], 0])
        reqs.append([cid, "ART", "T08", PRIMARY_PLAN["ART"], 1])
        reqs.append([cid, "AGR", "T08", PRIMARY_PLAN["AGR"], 0])
    teachers.append(["T07", names[6], "PE", 28, 6, "Thu:*"])
    teachers.append(["T08", names[7], "ART;AGR", 28, 6, "Mon:P2-P5"])
    rooms: list[list[object]] = [[c[3], f"Classroom {c[3][1:]}", "classroom", 45] for c in classes]
    rooms += [["SCI1", "Science Room", "science_room", 45], ["FLD1", "School Field", "field", 200]]
    return {
        "school.yaml": SCHOOL_YAML_PRIMARY,
        "subjects.csv": _csv(
            ["id", "name", "room_type", "room_use", "doubles", "heavy", "avoid_edges"],
            [
                [s[0], s[1], s[2], s[3], s[4], _yn(bool(s[5])), _yn(bool(s[6]))]
                for s in PRIMARY_SUBJECTS
            ],
        ),
        "rooms.csv": _csv(["id", "name", "type", "capacity"], rooms),
        "classes.csv": _csv(["id", "name", "size", "home_room"], [list(c) for c in classes]),
        "teachers.csv": _csv(
            ["id", "name", "subjects", "max_per_week", "max_per_day", "unavailable"], teachers
        ),
        "requirements.csv": _csv(["class", "subject", "teacher", "lessons", "doubles"], reqs),
    }


def write_inputs(files: dict[str, str], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")


def generate(kind: str) -> dict[str, str]:
    if kind == "secondary":
        return generate_secondary()
    if kind == "primary":
        return generate_primary()
    raise ValueError(f"unknown sample school '{kind}' (use 'secondary' or 'primary')")


def main() -> None:
    ap = argparse.ArgumentParser(description="Write the committed sample inputs.")
    ap.add_argument("--write-examples", metavar="DIR", required=True)
    args = ap.parse_args()
    root = Path(args.write_examples)
    write_inputs(generate_secondary(), root / "secondary")
    write_inputs(generate_primary(), root / "primary")
    print(f"wrote {root}/secondary and {root}/primary")


if __name__ == "__main__":
    main()
