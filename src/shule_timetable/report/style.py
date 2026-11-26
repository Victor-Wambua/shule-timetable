"""Stylesheet for the generated site: tokens, layout, grids, print rules."""

from __future__ import annotations

GOLDEN = 137.508

BASE_CSS = """
:root {
  --navy: #14213d;
  --amber: #fca311;
  --bg: #faf8f4;
  --surface: #ffffff;
  --surface-2: #f1eee7;
  --ink: #14213d;
  --muted: #545d72;
  --line: #d9d3c6;
  --accent: #fca311;
  --accent-ink: #14213d;
  --link: #14213d;
  --ok: #0b6b3a;
  --ok-bg: #e2f3e9;
  --bad: #9b1c1c;
  --bad-bg: #fbe3e3;
  --warn-bg: #fff3d6;
  --focus: #1d4ed8;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;
  --fs-0: 0.8125rem; --fs-1: 0.9375rem; --fs-2: 1.0625rem;
  --fs-3: 1.375rem; --fs-4: 1.875rem; --fs-5: 2.5rem;
  --radius: 10px;
  --font: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1526;
    --surface: #152039;
    --surface-2: #1c2a48;
    --ink: #e9edf5;
    --muted: #a5aec2;
    --line: #2d3c5e;
    --link: #ffd27a;
    --ok: #7be0a5;
    --ok-bg: #12301f;
    --bad: #ff9c9c;
    --bad-bg: #3a1618;
    --warn-bg: #3a2e12;
    --focus: #8ab4ff;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 400 var(--fs-1)/1.55 var(--font);
}
a { color: var(--link); text-underline-offset: 3px; }
a:hover { text-decoration-thickness: 2px; }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; border-radius: 4px; }
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}
.skip {
  position: absolute; left: var(--space-3); top: -60px; background: var(--accent);
  color: var(--accent-ink); padding: var(--space-2) var(--space-4); border-radius: var(--radius);
  z-index: 10; font-weight: 600;
}
.skip:focus { top: var(--space-3); }

/* ---- header ---- */
.top { background: var(--navy); color: #fff; }
.top-inner {
  max-width: 1180px; margin: 0 auto; padding: var(--space-3) var(--space-4);
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3) var(--space-5);
}
.brand { display: flex; align-items: center; gap: var(--space-2); color: #fff; text-decoration: none; font-weight: 700; letter-spacing: .01em; }
.brand svg { width: 28px; height: 28px; flex: none; }
.nav { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); margin-left: auto; }
.nav a { color: #e8ecf5; text-decoration: none; padding: var(--space-1) 0; border-bottom: 2px solid transparent; font-size: var(--fs-0); font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.nav a:hover, .nav a[aria-current="page"] { border-bottom-color: var(--accent); color: #fff; }
.top :focus-visible { outline-color: #fff; }

main { max-width: 1180px; margin: 0 auto; padding: var(--space-5) var(--space-4) var(--space-7); }
h1 { font-size: var(--fs-4); line-height: 1.15; margin: 0 0 var(--space-2); letter-spacing: -.01em; }
h2 { font-size: var(--fs-3); line-height: 1.2; margin: var(--space-6) 0 var(--space-3); letter-spacing: -.005em; }
h3 { font-size: var(--fs-2); margin: var(--space-4) 0 var(--space-2); }
p { margin: 0 0 var(--space-3); max-width: 70ch; }
.lede { font-size: var(--fs-2); color: var(--muted); max-width: 62ch; }
.muted { color: var(--muted); }
.crumbs { font-size: var(--fs-0); color: var(--muted); margin-bottom: var(--space-3); }

.badge {
  display: inline-block; font-size: var(--fs-0); font-weight: 700; padding: 2px var(--space-2);
  border-radius: 999px; background: var(--warn-bg); border: 1px solid var(--accent); color: var(--ink);
  vertical-align: middle;
}
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: var(--space-3) 0 var(--space-4); padding: 0; list-style: none; }
.chips li { background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 2px var(--space-3); font-size: var(--fs-0); }
.chips b { font-variant-numeric: tabular-nums; }

.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: var(--space-4); }
.cards { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.stat { font-size: var(--fs-4); font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.1; }
.stat-label { font-size: var(--fs-0); color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }

/* ---- proof panel ---- */
.proof { border: 2px solid var(--ok); background: var(--ok-bg); border-radius: var(--radius); padding: var(--space-4); }
.proof.fail { border-color: var(--bad); background: var(--bad-bg); }
.proof h2 { margin-top: 0; display: flex; gap: var(--space-2); align-items: center; }
.proof .tick { color: var(--ok); }
.proof.fail .tick { color: var(--bad); }
.rules { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; gap: var(--space-1) var(--space-5); grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.rules li { display: flex; gap: var(--space-2); align-items: baseline; font-size: var(--fs-0); }
.rules .mark { font-weight: 800; color: var(--ok); flex: none; width: 1.2em; }
.rules .bad .mark { color: var(--bad); }
.rules .n { margin-left: auto; color: var(--muted); font-variant-numeric: tabular-nums; flex: none; }
.violations { margin: var(--space-3) 0 0; color: var(--bad); font-size: var(--fs-0); }
.footnote { font-size: var(--fs-0); color: var(--muted); margin-top: var(--space-3); }

/* ---- finder ---- */
.finder { display: grid; gap: var(--space-3); grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); align-items: end; }
label { display: block; font-size: var(--fs-0); font-weight: 600; margin-bottom: var(--space-1); }
select, input[type=search] {
  width: 100%; min-height: 44px; font: inherit; color: var(--ink); background: var(--surface);
  border: 1px solid var(--muted); border-radius: 8px; padding: 0 var(--space-3);
}
button, .btn {
  min-height: 44px; font: inherit; font-weight: 700; padding: 0 var(--space-4); border-radius: 8px;
  border: 2px solid var(--navy); background: var(--accent); color: var(--accent-ink); cursor: pointer;
  text-decoration: none; display: inline-flex; align-items: center; justify-content: center;
}
button:hover, .btn:hover { filter: brightness(1.05); }
button.ghost, .btn.ghost { background: transparent; color: var(--ink); border-color: var(--line); }
.answer { margin-top: var(--space-4); min-height: 3.2em; padding: var(--space-3) var(--space-4); border-radius: var(--radius); background: var(--surface-2); border-left: 6px solid var(--accent); font-size: var(--fs-2); }
.answer b { font-weight: 700; }

/* ---- lists ---- */
.dir { display: grid; gap: var(--space-2); grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); list-style: none; margin: 0; padding: 0; }
.dir a { display: block; padding: var(--space-2) var(--space-3); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; text-decoration: none; min-height: 44px; }
.dir a:hover { border-color: var(--navy); }
.dir small { display: block; color: var(--muted); font-size: var(--fs-0); }
.table { width: 100%; border-collapse: collapse; font-size: var(--fs-0); }
.table th, .table td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--line); }
.table td.num, .table th.num { text-align: right; font-variant-numeric: tabular-nums; }
.bar { display: inline-block; height: 8px; border-radius: 4px; background: var(--accent); vertical-align: middle; min-width: 2px; }
.scroll { overflow-x: auto; }

/* ---- the weekly grid ---- */
table.grid { width: 100%; border-collapse: separate; border-spacing: 3px; table-layout: fixed; }
table.grid th { font-size: var(--fs-0); font-weight: 700; color: var(--muted); padding: var(--space-1); text-align: center; }
table.grid th.period { width: 76px; text-align: left; white-space: nowrap; }
table.grid th.period small { display: block; font-weight: 500; font-variant-numeric: tabular-nums; }
table.grid td { vertical-align: top; padding: 0; height: 64px; border-radius: 8px; }
table.grid tr.break th { height: 22px; background: repeating-linear-gradient(90deg, var(--surface-2) 0 6px, transparent 6px 12px); border-radius: 6px; font-size: 0.75rem; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); padding: 2px; }
td.free { background: transparent; border: 1px dashed var(--line); }
td.off, td.blocked { background: var(--surface-2); color: var(--muted); font-size: var(--fs-0); text-align: center; vertical-align: middle; }
.cell { display: block; height: 100%; padding: var(--space-2); border-radius: 8px; border-left: 5px solid var(--sbar); background-color: var(--sbg); color: var(--sfg); }
.cell .t { display: block; font-weight: 700; font-size: var(--fs-0); line-height: 1.25; }
.cell .s { display: block; font-size: 0.75rem; line-height: 1.3; opacity: .92; }
td.lesson { background: transparent; }

/* patterns: shape carries meaning too, not only colour */
.p0 { background-image: none; }
.p1 { background-image: repeating-linear-gradient(45deg, color-mix(in srgb, currentColor 14%, transparent) 0 2px, transparent 2px 9px); }
.p2 { background-image: radial-gradient(color-mix(in srgb, currentColor 22%, transparent) 1.3px, transparent 1.6px); background-size: 9px 9px; }
.p3 { background-image: repeating-linear-gradient(-45deg, color-mix(in srgb, currentColor 14%, transparent) 0 2px, transparent 2px 9px); }
.p4 { background-image: repeating-linear-gradient(0deg, color-mix(in srgb, currentColor 13%, transparent) 0 1.5px, transparent 1.5px 8px); }
.p5 { background-image: repeating-linear-gradient(90deg, color-mix(in srgb, currentColor 13%, transparent) 0 1.5px, transparent 1.5px 8px); }
.p6 { background-image: repeating-linear-gradient(45deg, color-mix(in srgb, currentColor 12%, transparent) 0 1.5px, transparent 1.5px 8px), repeating-linear-gradient(-45deg, color-mix(in srgb, currentColor 12%, transparent) 0 1.5px, transparent 1.5px 8px); }
.p7 { background-image: conic-gradient(color-mix(in srgb, currentColor 13%, transparent) 25%, transparent 0 50%, color-mix(in srgb, currentColor 13%, transparent) 0 75%, transparent 0); background-size: 12px 12px; }

/* phone view: a plain list per day instead of a squeezed grid */
.daylist { display: none; }
.daylist section { margin-bottom: var(--space-4); }
.daylist h3 { margin: 0 0 var(--space-2); font-size: var(--fs-2); }
.daylist ol { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.daylist li { display: grid; grid-template-columns: 64px 1fr; gap: var(--space-3); align-items: stretch; }
.daylist .when { font-size: var(--fs-0); color: var(--muted); font-variant-numeric: tabular-nums; padding-top: var(--space-2); }
.daylist .when b { display: block; color: var(--ink); }
.daylist .none { color: var(--muted); }
@media (max-width: 760px) {
  table.grid { display: none; }
  .daylist { display: block; }
  h1 { font-size: var(--fs-3); }
}

/* ---- master grid ---- */
.master-tools { display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center; margin: var(--space-3) 0; }
.seg { display: inline-flex; border: 2px solid var(--navy); border-radius: 8px; overflow: hidden; }
.seg button { border: 0; border-radius: 0; background: var(--surface); color: var(--ink); min-height: 40px; }
.seg button[aria-pressed="true"] { background: var(--navy); color: #fff; }
table.master { border-collapse: separate; border-spacing: 0; font-size: 0.75rem; }
table.master th, table.master td { border: 1px solid var(--line); padding: 0; text-align: center; min-width: 44px; height: 34px; }
table.master thead th { background: var(--surface-2); position: sticky; top: 0; z-index: 2; padding: 3px 2px; }
table.master th.rowh { position: sticky; left: 0; z-index: 3; background: var(--surface-2); text-align: left; padding: 3px var(--space-2); white-space: nowrap; min-width: 92px; }
table.master td.sepl, table.master th.sepl { border-left: 2px solid var(--muted); }
table.master td.dayend, table.master th.dayend { border-right: 2px solid var(--navy); }
table.master td a { display: block; height: 100%; padding: 2px; text-decoration: none; color: inherit; background-color: var(--sbg); color: var(--sfg); font-weight: 700; line-height: 1.15; }
table.master td a small { display: block; font-weight: 500; font-size: 0.6875rem; }
table.master td a > span { display: none; }
table.master.view-1 td a > .v1, table.master.view-2 td a > .v2, table.master.view-3 td a > .v3 { display: block; }
.legend { display: flex; flex-wrap: wrap; gap: var(--space-2); list-style: none; padding: 0; margin: var(--space-3) 0; }
.legend li { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--fs-0); }
.swatch { display: inline-block; width: 40px; height: 22px; border-radius: 5px; border-left: 5px solid var(--sbar); background-color: var(--sbg); color: var(--sfg); }

footer { max-width: 1180px; margin: 0 auto; padding: var(--space-4); color: var(--muted); font-size: var(--fs-0); border-top: 1px solid var(--line); }
footer .tick { color: var(--ok); font-weight: 800; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; scroll-behavior: auto !important; } }

/* ---- print: A4 landscape, ink-friendly ---- */
@page { size: A4 landscape; margin: 10mm; }
@media print {
  :root { color-scheme: light; --bg: #fff; --surface: #fff; --ink: #000; --muted: #333; --line: #888; }
  body { background: #fff; font-size: 10pt; }
  .top, .skip, .nav, .master-tools, .no-print, footer .no-print, .finder, .answer { display: none !important; }
  main { padding: 0; max-width: none; }
  h1 { font-size: 18pt; }
  .chips li { border-color: #666; }
  table.grid { display: table !important; border-spacing: 2px; }
  table.grid td { height: 15mm; }
  .daylist { display: none !important; }
  .cell { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .scroll { overflow: visible; }
  table.master { font-size: 6.5pt; width: 100%; table-layout: fixed; }
  table.master th, table.master td { min-width: 0; height: 9mm; }
  table.master th.rowh { position: static; min-width: 20mm; }
  table.master thead th { position: static; }
  table.master td a, .cell, .swatch { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .proof { break-inside: avoid; }
  a { color: inherit; text-decoration: none; }
}
"""


def subject_css(n: int) -> str:
    """Per-subject colour tokens (light + dark) and the pattern each subject uses."""
    light: list[str] = []
    dark: list[str] = []
    for i in range(n):
        hue = round((i * GOLDEN) % 360)
        light.append(
            f".s{i} {{ --sbg: hsl({hue} 72% 91%); --sfg: hsl({hue} 60% 15%); --sbar: hsl({hue} 70% 42%); }}"
        )
        dark.append(
            f"  .s{i} {{ --sbg: hsl({hue} 38% 23%); --sfg: hsl({hue} 80% 91%); --sbar: hsl({hue} 75% 62%); }}"
        )
    return (
        "\n".join(light) + "\n@media (prefers-color-scheme: dark) {\n" + "\n".join(dark) + "\n}\n"
    )


def build_css(n_subjects: int) -> str:
    return BASE_CSS + "\n" + subject_css(max(1, n_subjects))
