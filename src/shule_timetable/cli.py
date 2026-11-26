"""Command line: ``shule-timetable validate | solve | explain | report | repair | demo``."""

from __future__ import annotations

import argparse
import dataclasses
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version as pkg_version
from pathlib import Path

from . import __version__
from .demo import generate, write_inputs
from .explain import binding_constraints, explain_infeasible
from .issues import InputError, Issue, errors_of
from .loader import load_with_issues
from .model import School, Timetable
from .prechecks import run_prechecks
from .repair import RepairResult, load_changes, repair
from .report import build_site
from .scoring import ScoreBreakdown
from .solver import SolveResult, SolveSettings, solve
from .storage import load_timetable, save_timetable
from .validator import validate


def machine_label() -> str:
    cpu = ""
    try:
        if platform.system() == "Darwin":
            cpu = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
        elif Path("/proc/cpuinfo").exists():
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    cpu = cpu or platform.machine()
    return f"{cpu}, {os.cpu_count()} cores, {platform.system()} {platform.machine()}"


def _print_issues(issues: list[Issue]) -> None:
    for i in issues:
        print(i, file=sys.stderr if i.severity == "error" else sys.stdout)


def _load(path: str) -> School | None:
    school, issues = load_with_issues(path)
    _print_issues(issues)
    if school is None:
        n = len(errors_of(issues))
        print(f"\n{n} error(s) in the input. Fix them and run again.", file=sys.stderr)
    return school


def _meta(result: SolveResult, settings: SolveSettings) -> dict[str, object]:
    return {
        "status": result.status,
        "objective": result.objective,
        "best_bound": result.best_bound,
        "gap": result.gap,
        "wall_time_s": round(result.wall_time, 2),
        "workers": settings.workers or os.cpu_count(),
        "seed": settings.seed,
        "time_limit_s": settings.time_limit,
        "machine": machine_label(),
        "ortools": pkg_version("ortools"),
        "model_variables": result.stats.get("variables"),
        "model_constraints": result.stats.get("constraints"),
        "solver_version": f"shule-timetable {__version__}",
    }


def _print_breakdown(b: ScoreBreakdown) -> None:
    print("\nSoft-rule score (lower is better):")
    for i in sorted(b.items, key=lambda x: -x.penalty):
        print(f"  {i.label:<52} {i.count:>5} x {i.weight:<3} = {i.penalty:>5}")
    print(f"  {'Total penalty':<52} {'':>5}   {'':<3}   {b.total:>5}")


def _print_validation(school: School, tt: Timetable) -> bool:
    rep = validate(school, tt)
    print(f"\nIndependent validator: {rep.checks:,} checks")
    for r in rep.rules:
        print(f"  {'OK  ' if r.ok else 'FAIL'} {r.title} ({r.checked:,})")
        for v in r.violations[:10]:
            print(f"       - {v}")
    return rep.ok


def cmd_validate(args: argparse.Namespace) -> int:
    school = _load(args.dir)
    if school is None:
        return 1
    pre = run_prechecks(school)
    _print_issues(pre)
    print(
        f"\n{school.name}: {len(school.classes)} classes, {len(school.teachers)} teachers, "
        f"{len(school.rooms)} rooms, {sum(r.lessons for r in school.requirements)} lessons a week "
        f"into {len(school.calendar.slots)} slots."
    )
    if args.solution:
        tt = load_timetable(args.solution, school)
        return 0 if _print_validation(school, tt) and not errors_of(pre) else 1
    if errors_of(pre):
        print(
            f"\n{len(errors_of(pre))} problem(s) make a timetable impossible; see above.",
            file=sys.stderr,
        )
        return 1
    print("Input is valid and passes the infeasibility pre-checks.")
    return 0


def _settings(args: argparse.Namespace) -> SolveSettings:
    return SolveSettings(
        time_limit=args.time_limit,
        seed=args.seed,
        workers=args.workers,
        log=getattr(args, "log", False),
    )


def cmd_solve(args: argparse.Namespace) -> int:
    school = _load(args.dir)
    if school is None:
        return 1
    pre = errors_of(run_prechecks(school))
    if pre:
        _print_issues(pre)
        print("\nNo timetable can exist. Run 'explain' for details.", file=sys.stderr)
        return 1
    settings = _settings(args)
    print(f"Solving (time limit {settings.time_limit:g}s, seed {settings.seed}) ...")
    result = solve(school, settings)
    if result.timetable is None:
        print(
            f"No timetable found (status {result.status}). Run 'explain' to see why.",
            file=sys.stderr,
        )
        return 2
    tt = dataclasses.replace(result.timetable, meta=_meta(result, settings))
    save_timetable(args.output, school, tt)
    gap = f"{result.gap * 100:.1f}%" if result.gap is not None else "n/a"
    print(
        f"Status {result.status} in {result.wall_time:.1f}s; objective {result.objective:g}, "
        f"proven bound {result.best_bound:g}, gap {gap}."
    )
    if result.breakdown:
        _print_breakdown(result.breakdown)
    ok = _print_validation(school, tt)
    print(f"\nWrote {args.output}")
    return 0 if ok else 3


def cmd_explain(args: argparse.Namespace) -> int:
    school = _load(args.dir)
    if school is None:
        return 1
    exp = explain_infeasible(school, time_limit=args.time_limit, seed=args.seed)
    print(exp.render())
    if exp.status == "infeasible":
        return 2
    if exp.status == "feasible":
        tt: Timetable | None = None
        if args.solution:
            tt = load_timetable(args.solution, school)
        else:
            res = solve(school, SolveSettings(time_limit=min(args.time_limit, 20), seed=args.seed))
            tt = res.timetable
        if tt is not None:
            print("\nWhat limits the timetable (resources close to full):")
            for b in binding_constraints(school, tt)[:12]:
                print(f"  {b.utilisation * 100:5.1f}%  {b.text}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    school = _load(args.dir)
    if school is None:
        return 1
    tt = load_timetable(args.solution, school)
    rep = build_site(school, tt, args.out)
    print(f"Wrote site to {args.out}/index.html")
    if not rep.ok:
        print(
            f"WARNING: validator found {len(rep.violations)} violation(s); the site says so.",
            file=sys.stderr,
        )
        return 3
    print(f"Validator: no violations in {rep.checks:,} checks.")
    return 0


def _print_repair(res: RepairResult) -> None:
    s = res.school
    cal = s.calendar
    print(
        f"Status {res.status}; minimum proven: {'yes' if res.minimal_proven else 'no (time limit)'}"
    )
    changed = res.moved + res.added
    print(
        f"\n{changed} of {res.total_lessons + res.added} lesson periods differ from the old timetable "
        f"({res.moved} moved, {res.added} new)."
    )
    if res.teacher_changed:
        print(f"{res.teacher_changed} lesson periods keep their slot but get a new teacher.")
    if res.room_changes:
        print(f"{res.room_changes} lessons keep their slot but change room.")
    if res.scratch_moved is not None:
        print(f"For comparison, re-solving from scratch moves {res.scratch_moved} lesson periods.")
    for m in res.moves:
        label = f"{s.classes[m.class_id].name} {s.subjects[m.subject_id].name}"
        if m.kind == "moved":
            before = cal.label(m.before) if m.before else "?"
            after = cal.label(m.after) if m.after else "removed"
            print(f"  moved   {label}: {before} -> {after}")
        elif m.kind == "added":
            print(f"  added   {label}: {cal.label(m.after) if m.after else ''}")
        elif m.kind == "teacher":
            print(f"  teacher {label} at {cal.label(m.before) if m.before else ''}: {m.detail}")
        else:
            print(f"  room    {label} at {cal.label(m.before) if m.before else ''}: {m.detail}")


def cmd_repair(args: argparse.Namespace) -> int:
    school = _load(args.dir)
    if school is None:
        return 1
    old = load_timetable(args.solution, school)
    changes = load_changes(args.change)
    print("Changes:")
    for c in changes:
        print(f"  - {c.describe()}")
    res = repair(school, old, changes, _settings(args), compare_scratch=args.compare_scratch)
    if res.timetable is None:
        print(
            f"\nNo repaired timetable found (status {res.status}). Running explain on the changed school:"
        )
        print(explain_infeasible(res.school, time_limit=args.time_limit).render())
        return 2
    print()
    _print_repair(res)
    meta = dict(old.meta)
    meta.update(
        {
            "repaired_from": str(args.solution),
            "status": res.status,
            "gap": None,
            "wall_time_s": round(res.wall_time, 2),
            "machine": machine_label(),
        }
    )
    new = dataclasses.replace(res.timetable, meta=meta)
    ok = _print_validation(res.school, new)
    if args.output:
        save_timetable(args.output, res.school, new)
        print(f"\nWrote {args.output}")
    if args.out:
        build_site(res.school, new, args.out)
        print(f"Wrote site to {args.out}/index.html")
    return 0 if ok else 3


def cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    input_dir = out / "input"
    write_inputs(generate(args.school), input_dir)
    print(f"Generated the synthetic {args.school} school in {input_dir}")
    school = _load(str(input_dir))
    if school is None:
        return 1
    errs = errors_of(run_prechecks(school))
    if errs:
        _print_issues(errs)
        return 1
    settings = _settings(args)
    print(
        f"{len(school.classes)} classes, {len(school.teachers)} teachers, "
        f"{sum(r.lessons for r in school.requirements)} lessons into {len(school.calendar.slots)} slots. "
        f"Solving for up to {settings.time_limit:g}s ..."
    )
    result = solve(school, settings)
    if result.timetable is None:
        print(f"No timetable found (status {result.status}).", file=sys.stderr)
        return 2
    tt = dataclasses.replace(result.timetable, meta=_meta(result, settings))
    save_timetable(out / "solution.json", school, tt)
    gap = f"{result.gap * 100:.1f}%" if result.gap is not None else "n/a"
    print(
        f"Solved: status {result.status} in {result.wall_time:.1f}s on {machine_label()} "
        f"(gap to proven bound {gap})."
    )
    if result.breakdown:
        _print_breakdown(result.breakdown)
    ok = _print_validation(school, tt)
    build_site(school, tt, out / "site")
    print(f"\nOpen {out / 'site' / 'index.html'} in a browser.")
    return 0 if ok else 3


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="shule-timetable", description="Clash-free school timetables from plain CSV/YAML."
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    def solver_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument("--time-limit", type=float, default=60.0, help="seconds (default 60)")
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--workers", type=int, default=0, help="0 = all cores; 1 = deterministic")

    p = sub.add_parser("validate", help="check the input files (and optionally a solution)")
    p.add_argument("dir")
    p.add_argument("--solution", help="also run the independent validator on this solution.json")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("solve", help="build a timetable")
    p.add_argument("dir")
    p.add_argument("-o", "--output", default="solution.json")
    solver_opts(p)
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("explain", help="why is there no timetable / what limits it")
    p.add_argument("dir")
    p.add_argument("--solution")
    solver_opts(p)
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("report", help="render the static HTML site, CSV and ICS")
    p.add_argument("dir")
    p.add_argument("--solution", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("repair", help="apply a change, moving as few lessons as possible")
    p.add_argument("dir")
    p.add_argument("--solution", required=True)
    p.add_argument("--change", required=True, help="YAML file with a 'changes:' list")
    p.add_argument("-o", "--output", help="write the repaired solution.json here")
    p.add_argument("--out", help="also render the repaired site here")
    p.add_argument("--compare-scratch", action="store_true", help="also re-solve from scratch")
    solver_opts(p)
    p.set_defaults(func=cmd_repair)

    p = sub.add_parser("demo", help="generate a synthetic school, solve it, render the site")
    p.add_argument("--school", choices=["secondary", "primary"], default="secondary")
    p.add_argument("--out", default="out/demo")
    solver_opts(p)
    p.set_defaults(func=cmd_demo)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        code = args.func(args)
    except InputError as e:
        _print_issues(e.issues)
        code = 1
    sys.exit(code)


_ = (shutil, tempfile)

if __name__ == "__main__":
    main()
