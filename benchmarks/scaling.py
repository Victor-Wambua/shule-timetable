"""Measure how solve time grows with school size, on this machine.

    python benchmarks/scaling.py [--time-limit 30] [--streams 1 2 3 4 5 6]

For each size: time to the first feasible timetable, the soft score reached by 10 s and at
the limit, and the gap to the solver's proven bound. Output is a Markdown table.
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

from ortools.sat.python import cp_model

from shule_timetable.cli import machine_label
from shule_timetable.demo import generate_secondary, write_inputs
from shule_timetable.loader import load_school
from shule_timetable.solver import ModelBuilder, SolveSettings, configure


class Trace(cp_model.CpSolverSolutionCallback):
    def __init__(self) -> None:
        super().__init__()
        self.t0 = time.perf_counter()
        self.points: list[tuple[float, float]] = []

    def on_solution_callback(self) -> None:
        self.points.append((time.perf_counter() - self.t0, self.objective_value))

    def at(self, seconds: float) -> float | None:
        best = None
        for t, obj in self.points:
            if t <= seconds:
                best = obj
        return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-limit", type=float, default=30.0)
    ap.add_argument("--streams", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6])
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()
    print(
        f"Measured on {machine_label()}; time limit {args.time_limit:g}s per size; workers {args.workers or 'auto'}\n"
    )
    print(
        "| classes | teachers | lessons/wk | model vars | first feasible | score @10s | score @limit | gap | status |"
    )
    print("|---:|---:|---:|---:|---:|---:|---:|---:|:--|")
    for streams in args.streams:
        with tempfile.TemporaryDirectory() as d:
            write_inputs(generate_secondary(streams=streams), Path(d))
            school = load_school(d)
        built = time.perf_counter()
        b = ModelBuilder(school)
        build_s = time.perf_counter() - built
        solver = cp_model.CpSolver()
        configure(solver, SolveSettings(time_limit=args.time_limit, workers=args.workers))
        trace = Trace()
        status = solver.solve(b.model, trace)
        name = solver.status_name(status)
        if not trace.points:
            print(
                f"| {len(school.classes)} | {len(school.teachers)} | - | - | none | - | - | - | {name} |"
            )
            continue
        obj, bound = solver.objective_value, solver.best_objective_bound
        gap = (obj - bound) / obj * 100 if obj else 0.0
        at10 = trace.at(10)
        lessons = sum(r.lessons for r in school.requirements)
        print(
            f"| {len(school.classes)} | {len(school.teachers)} | {lessons} | {len(b.model.proto.variables):,} "
            f"| {trace.points[0][0] + build_s:.1f}s | {at10:.0f} | {obj:.0f} | {gap:.0f}% | {name} |"
        )


if __name__ == "__main__":
    main()
