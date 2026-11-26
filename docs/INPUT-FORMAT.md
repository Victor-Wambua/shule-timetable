# Input format

A school is one folder with six files. Open them in any spreadsheet or text editor.
`examples/secondary/` is a complete working example; `shule-timetable validate <folder>`
checks a folder and points at the file and line of every mistake.

## school.yaml

```yaml
name: Mwangaza Hills Secondary School
synthetic: true                # optional; adds a "synthetic sample data" label to the pages
term: {start: 2026-01-05, weeks: 13}   # used for calendar (.ics) files

days: [Mon, Tue, Wed, Thu, Fri]
periods:                       # lesson periods in order; breaks are not periods
  - {label: P1, start: "08:00", end: "08:40"}
  - {label: P2, start: "08:40", end: "09:20"}
breaks:                        # a break sits AFTER the named period
  - {after: P2, name: Tea}
  - {after: P6, name: Lunch, long: true}
short_days: {Fri: 6}           # Friday has periods P1-P6 only
blocked: ["Wed:P8"]            # no lessons for anyone (assembly, clubs)

limits:
  max_per_subject_per_day: 2   # per class; a subject can override with max_per_day
  max_consecutive_lessons: 3   # more than this in a row counts against the timetable
  morning_until: P4            # last period that counts as "morning"
light_slots: ["Fri:P5-P6"]     # slots to keep light (soft)
weights: {teacher_gaps: 2}     # any subset of the soft-rule weights below
```

**Slot specs** are used for `unavailable`, `blocked`, `light_slots` and repair changes:
`Mon:P1`, `Mon:P1-P3`, `Mon-Wed:P7,P8`, `Fri:*`, joined with `;`. Day names and period labels
are whatever you defined above.

**Breaks.** Every break stops a double lesson from straddling it. Only a `long: true` break
(lunch) also ends a "stretch" of back-to-back teaching for the consecutive-lessons rule.

## subjects.csv

| column | meaning |
|---|---|
| `id`, `name` | required |
| `room_type` | `home` (default: the class's own classroom) or a specialist type such as `chem_lab`, `field` |
| `room_use` | `all` (every lesson uses `room_type`) or `doubles` (only the double lessons: practicals in the lab, theory at home) |
| `doubles` | default number of double lessons per week for each class |
| `heavy` | `yes` = prefer the morning (soft) |
| `avoid_edges` | `yes` = avoid the first and last period of the day (soft) |
| `max_per_day` | per-class daily limit for this subject (default from `limits`) |

## rooms.csv, classes.csv

`rooms.csv`: `id,name,type,capacity`. `classes.csv`: `id,name,size,home_room`. Every class has its
own home room. A specialist lesson is only given a room of the right type whose capacity
covers the class size. Classroom types must not also be used as a subject `room_type`.

## teachers.csv

`id,name,subjects,max_per_week,max_per_day,unavailable`. `subjects` is a `;`-separated list of
subject ids the teacher is qualified for. `max_per_day` and `unavailable` are optional.

## requirements.csv

`class,subject,teacher,lessons,doubles`. One row per class and subject: how many periods a week,
which teacher, and how many of those periods are paired into two-period double lessons
(blank = the subject's default). **Who teaches what is an input**, as it is in a real school:
the head decides staffing, the timetable fits lessons around it.

## Soft-rule weights

Penalty per occurrence; `0` switches a rule off. The solver minimises the total.

| weight | counted per | default |
|---|---|---:|
| `class_gaps` | free period in the middle of a class's day | 8 |
| `teacher_consecutive` | window of more than `max_consecutive_lessons` back-to-back lessons | 6 |
| `spread_subjects` | day missing from an even spread of a subject across the week | 4 |
| `heavy_morning` | `heavy` lesson after `morning_until` | 3 |
| `avoid_edges` | flagged lesson in the first or last period | 3 |
| `teacher_gaps` | idle period between a teacher's first and last lesson of a day | 2 |
| `balance_daily_load` | lesson above an even daily share for a class | 2 |
| `light_slots` | lesson in a `light_slots` slot | 2 |
| `teacher_days_compact` | working day beyond the fewest the teacher's load could fit in | 1 |

## Repair changes

A YAML file with a `changes:` list, each item a single-key mapping:

```yaml
changes:
  - unavailable: {teacher: T09, slots: "Wed:*"}
  - leave: {teacher: T16, replacement: T17}          # unavailable everywhere + all classes move
  - reassign: {from: T16, to: T18, class: 4S}        # optional class: / subject: filters
  - add_lesson: {class: 2N, subject: MAT, count: 1}  # add teacher: if the class has none yet
  - set_max_per_week: {teacher: T17, value: 30}
```
