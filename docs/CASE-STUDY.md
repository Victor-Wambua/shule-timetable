# Case study: Shule Timetable

## The problem

In many schools the timetable is one person's job: usually a deputy head, usually for days
at the start of each term, usually on paper or in Excel. They are tracking teachers who
can only come on certain days, a single chemistry lab, double lessons that cannot straddle
tea, and a rule of thumb that nobody gets eight lessons back to back. One clash found on
Monday morning, or one teacher leaving mid-term, can mean starting again. The real cost is
not the first draft. It is every change afterwards, because each change disturbs lessons
that were fine.

## Goals and non-goals

Goals: take plain CSV/YAML a deputy head can edit; produce a timetable that provably breaks
no hard rule; say in plain English why when no timetable exists; and change as little as
possible when something changes mid-term.

Non-goals: no curriculum is baked in (you supply the lessons per week); no automatic teacher
allocation (who teaches which class is a staffing decision, so it is an input); no web
editor; not field-tested with a real school.

## What I built

A Python package and CLI. `solve` builds a timetable with Google OR-Tools CP-SAT. `explain`
diagnoses an impossible input. `repair` re-solves after a change. `report` writes a
static site: a page per class, teacher and room, a master grid, CSV and calendar files.
Every page carries a tick from a separate validator (see the screenshot in the README).

## Design decisions and trade-offs

**1. CP-SAT, not a hand-rolled search.** I wrote a first-fit greedy timetabler as a
benchmark (`benchmarks/greedy.py`): hardest lessons first, first free slot, no backtracking.
On the sample secondary school (16 classes, 556 lesson periods a week) it leaves 12 periods
unplaced, and 7 of 16 classes end up short of lessons. It places everything on the looser
six-class primary sample, but the soft-rule penalty of its result is 550 against 96 for the
solver. A greedy pass cannot undo an early choice, and timetabling is mostly about undoing
early choices. CP-SAT backtracks, learns from conflicts, and improves a solution with
large-neighbourhood search. The cost is a dependency and a model to maintain.

**2. Event-start variables, so doubles are cheap.** For each class-and-subject and each
slot there are two 0/1 variables: a single lesson starts here, or a double starts here. A
double is only offered where the next period is in the same break-free segment, so "not
across tea or lunch" is built into the variables and needs no extra constraint. "Occupies
this slot" is then a sum, and every clash rule is "this sum is at most one". The
alternative, one variable per lesson per slot with adjacency constraints, was simpler to
write but made doubles and breaks a separate set of rules to get wrong. Room assignment is
a third layer, only for lessons that need a specialist room. Theory lessons for sciences stay
in the classroom; only the practical double goes to the lab.

**3. Hard versus soft, and where the weights came from.** Anything that makes the timetable
unusable is hard. Anything a teacher would grumble about is soft: spread across the week,
long back-to-back runs, idle gaps, heavy subjects in the morning, balanced days, free days.
The default weights are ordered by how much I think each hurts (a free period in the middle
of a class's day, 8, down to a teacher's extra working day, 1). I did not fit them to data.
They are a defensible starting point, they live in `school.yaml`, and each rule can be
switched off. Every soft rule has a test whose optimum I worked out by hand, for example a
teacher free only at P1 and P4 must cost exactly two idle periods.

**4. Two ways of knowing the score.** The solver minimises the objective inside CP-SAT. A
second implementation, `scoring.py`, recomputes it in plain Python from the finished
timetable. For any instance solved to optimality they must agree, and a test checks that.
This caught a design flaw early: my first "compact free days" rule charged every working
day, so almost every teacher cost five points whatever the solver did (142 of 678 penalty points in one early run), and the proven
bound was meaningless. I redefined it as days beyond the fewest the teacher's load fits in.

**5. Explanations from unsat cores.** Each hard rule (a class's lesson count, a teacher's
availability, a room type) sits behind its own assumption literal. When CP-SAT proves the
model infeasible it returns a conflicting subset; I then drop rules one at a time and
re-solve, which gives a minimal set when every re-solve finishes in time. The test school
is two teachers who are each free only for the same single double period, plus one lab.
Every pre-check passes (each resource alone is fine), the solver proves it impossible, and
the core names exactly those five rules.

**6. Repair as a lexicographic problem.** After a change, stage one minimises lessons moved,
then room switches among lessons that stayed; stage two keeps both minima and improves the
soft score. My first version only minimised moves and then optimised soft rules, which
left 17 needless room switches, because nothing in the soft score cares about rooms. Making
room switches part of stage one fixed it. On the sample school, when a chemistry teacher
leaves and two colleagues take their classes, 13 of 556 lesson periods move (proven
minimum); re-solving from scratch moves about 500. A maths teacher losing Wednesdays moves 5;
an extra lesson moves none. These are single runs on synthetic data, not a study.

## How it is kept correct and safe

The validator (`validator.py`) imports nothing from the solver. It walks the lessons with
plain loops and checks twelve rules, and it has a test per rule with a hand-built
violating timetable. A property test generates small random schools and asserts that
anything the solver returns passes the validator. Input errors are collected, not raised
one at a time, with a file and line ("requirements.csv:14: class 'G33' is not in
classes.csv. Did you mean 'G3'?"). The site is generated with every value escaped. A test
caught my own mistake there: a teacher name containing `<script>` reached the embedded JSON
for the finder unescaped; it is now escaped. The pages load no external scripts or fonts.

What the tick does not mean: it proves the timetable obeys the rules in the input, not that
the input describes your school. A wrong `max_per_week` produces a perfect timetable for the
wrong school.

## Solve time, measured

On an Apple M4 (10 cores), synthetic secondary schools of growing size, 30 s per run:

| classes | lessons/wk | first feasible | penalty at 10 s | at 30 s |
|---:|---:|---:|---:|---:|
| 4 | 138 | 0.2 s | 83 | 77 |
| 8 | 277 | 0.3 s | 278 | 227 |
| 12 | 417 | 0.6 s | 546 | 378 |
| 16 | 556 | 0.7 s | 795 | 639 |
| 24 | 833 | 1.1 s | 1532 | 1135 |

Finding any valid timetable is fast. Finding a good one is not: no run proved optimality,
and the gap to the solver's bound stays large (74% for the 16-class sample after 120 s,
with penalty 522 and bound 134). The bound is weak because the soft rules interact through
many small penalties; the penalty keeps falling with more time. Treat the penalty as "good
enough to publish and edit by hand", not as the best possible.

## What I would do differently

Let the solver choose teachers among qualified candidates (the model would gain a layer of
variables and repair would be able to answer "who should take over?"). Add per-teacher
preferences instead of only global weights. Stronger lower bounds, so a user can tell
"close to the best" from "far from it". And, above all, try it on a real school's
requirements.

## Status

Portfolio build. All data is synthetic and labelled. Solve times are from one laptop. Tests
use no network. The calendar files and print layout were checked in a browser and by unit
tests, not on a printer or in a calendar app.
