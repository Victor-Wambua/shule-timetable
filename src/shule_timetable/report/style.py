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
  --bad: #9b1c1c;
  --focus: #1d4ed8;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;
  --fs-0: 0.875rem; --fs-1: 1rem; --fs-2: 1.125rem;
  --fs-3: 1.5rem; --fs-4: 2.125rem;
  --radius: 6px;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
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
    --bad: #ff9c9c;
    --focus: #8ab4ff;
    color-scheme: dark;
  }
  .seg { border-color: var(--muted); }
  .seg-opt + .seg-opt span { border-left-color: var(--muted); }
  .seg-opt input:checked + span { background: var(--accent); color: var(--accent-ink); }
  .seg-opt input:checked:focus-visible + span { outline-color: var(--focus); }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
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
  max-width: 1180px; margin: 0 auto; padding: var(--space-2) var(--space-4);
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-1) var(--space-6);
}
.brand { display: flex; align-items: center; gap: var(--space-2); color: #fff; text-decoration: none; font-weight: 700; font-size: var(--fs-2); min-height: 44px; }
.brand svg { width: 28px; height: 28px; flex: none; }
.nav { display: flex; flex-wrap: wrap; gap: 0 var(--space-5); margin-left: auto; }
.nav a { color: #e8ecf5; text-decoration: none; display: inline-flex; align-items: center; min-height: 40px; border-bottom: 3px solid transparent; border-top: 3px solid transparent; font-size: var(--fs-1); font-weight: 500; }
.nav a:hover { color: #fff; border-bottom-color: #8d97ad; }
.nav a[aria-current] { color: #fff; font-weight: 700; border-bottom-color: var(--accent); }
.top :focus-visible { outline-color: #fff; }

main { max-width: 1180px; margin: 0 auto; padding: var(--space-5) var(--space-4) var(--space-7); }
main:focus { outline: none; }
h1, h2, h3 { font-family: var(--serif); font-weight: 700; }
h1 { font-size: var(--fs-4); line-height: 1.15; margin: 0 0 var(--space-2); }
h2 { font-size: var(--fs-3); line-height: 1.2; margin: var(--space-7) 0 var(--space-3); }
h3 { font-size: var(--fs-2); margin: var(--space-4) 0 var(--space-2); }
p { margin: 0 0 var(--space-3); max-width: 70ch; }
.lede { font-size: var(--fs-2); color: var(--muted); max-width: 62ch; }
.muted, .hint { color: var(--muted); }
.hint { font-size: var(--fs-0); margin-top: var(--space-2); }
.dataline { font-size: var(--fs-0); color: var(--muted); margin: 0 0 var(--space-3); }
.dataline b { color: var(--ink); }
.crumbs { margin-bottom: var(--space-2); }
.crumbs a, .tl { display: inline-flex; align-items: center; min-height: 32px; font-size: var(--fs-0); }
.tl { font-size: inherit; }
@media (pointer: coarse) { .crumbs a, .tl, footer a { min-height: 44px; } }

.facts { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-5); margin: var(--space-3) 0 var(--space-4); padding: var(--space-2) 0; border-block: 1px solid var(--line); list-style: none; }
.facts b { font-variant-numeric: tabular-nums; }
.figures { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-1) var(--space-6); margin: var(--space-5) 0 0; padding: var(--space-3) 0; border-block: 1px solid var(--line); list-style: none; color: var(--muted); }
.figures b { font: 700 1.875rem/1.1 var(--serif); font-variant-numeric: tabular-nums lining-nums; color: var(--ink); }

/* ---- proof panel: one rule, one accent ---- */
.proof { border-left: 4px solid var(--ok); padding-left: var(--space-4); margin: var(--space-6) 0 0; }
.proof.fail { border-left-color: var(--bad); }
.proof h2 { margin: 0 0 var(--space-2); display: flex; gap: var(--space-2); align-items: baseline; }
.proof .tick { color: var(--ok); }
.proof.fail .tick { color: var(--bad); }
.rules { border-collapse: collapse; width: 100%; max-width: 48rem; margin: var(--space-3) 0 0; font-size: var(--fs-0); }
.rules th, .rules td { padding: 6px var(--space-2) 6px 0; border-top: 1px solid var(--line); text-align: left; font-weight: 400; vertical-align: baseline; }
.rules thead th { color: var(--muted); font-weight: 600; border-top: 0; padding-top: 0; }
.rules .mark { display: inline-block; width: 1.4em; font-weight: 800; color: var(--ok); }
.rules .bad .mark { color: var(--bad); }
.rules .n { text-align: right; font-variant-numeric: tabular-nums; padding-right: 0; white-space: nowrap; }
.violations { margin: var(--space-3) 0 0; color: var(--bad); font-size: var(--fs-0); }
.footnote { font-size: var(--fs-0); color: var(--muted); margin-top: var(--space-3); }

/* ---- finder ---- */
.fields { display: grid; gap: var(--space-3); grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); align-items: end; max-width: 56rem; }
label { display: block; font-size: var(--fs-0); font-weight: 600; margin-bottom: var(--space-1); }
select, input[type=search] {
  width: 100%; min-height: 44px; font: inherit; color: var(--ink); background: var(--surface);
  border: 1px solid var(--muted); border-radius: var(--radius); padding: 0 var(--space-3);
}
button, .btn {
  min-height: 44px; font: inherit; font-weight: 700; padding: 0 var(--space-4); border-radius: var(--radius);
  border: 2px solid var(--navy); background: var(--accent); color: var(--accent-ink); cursor: pointer;
  text-decoration: none; display: inline-flex; align-items: center; justify-content: center;
}
button:hover, .btn:hover { filter: brightness(1.05); }
button.ghost, .btn.ghost { background: transparent; color: var(--ink); border-color: var(--muted); }
.answer { margin-top: var(--space-4); padding: var(--space-3) var(--space-4); border-left: 4px solid var(--accent); background: var(--surface-2); font-size: var(--fs-2); max-width: 56rem; }
.answer:empty { display: none; }
.answer b { font-weight: 700; }
.answer .assume { display: block; font-size: var(--fs-0); color: var(--muted); margin-bottom: var(--space-1); }

/* ---- lists ---- */
.dir { display: grid; gap: 0 var(--space-6); grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); list-style: none; margin: 0; padding: 0; }
.dir li { border-top: 1px solid var(--line); }
.dir a { display: block; padding: var(--space-2) 0; text-decoration: none; min-height: 44px; }
.dir a:hover { text-decoration: underline; }
.dir small { display: block; color: var(--muted); font-size: var(--fs-0); }
.plain { padding-left: 0; list-style: none; }
.plain li { padding: var(--space-1) 0; }
.table { width: 100%; border-collapse: collapse; font-size: var(--fs-0); }
.table th, .table td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--line); }
.table thead th { color: var(--muted); }
.table tbody th { font-weight: 400; }
.table td.num, .table th.num { text-align: right; font-variant-numeric: tabular-nums; }
.bar { display: inline-block; height: 8px; border-radius: 4px; background: var(--accent); vertical-align: middle; min-width: 2px; }
.scroll { overflow-x: auto; position: relative; }

/* ---- the weekly grid ---- */
table.grid { width: 100%; border-collapse: separate; border-spacing: 3px; table-layout: fixed; }
table.grid th { font-size: var(--fs-0); font-weight: 700; color: var(--muted); padding: var(--space-1); text-align: center; }
table.grid th.period { width: 80px; text-align: left; white-space: nowrap; }
table.grid th.period small { display: block; font-weight: 500; font-size: var(--fs-0); font-variant-numeric: tabular-nums; }
table.grid td { vertical-align: top; padding: 0; height: 68px; border-radius: var(--radius); }
table.grid tr.break td { height: 26px; background: repeating-linear-gradient(90deg, var(--surface-2) 0 6px, transparent 6px 12px); font-size: var(--fs-0); color: var(--muted); padding: 2px; text-align: center; vertical-align: middle; }
td.free { background: transparent; border: 1px dashed var(--line); }
td.off, td.blocked { background: var(--surface-2); color: var(--muted); font-size: var(--fs-0); text-align: center; vertical-align: middle; }
.cell { display: block; height: 100%; padding: var(--space-2); border-radius: var(--radius); border-left: 5px solid var(--sbar); background-color: var(--sbg); color: var(--sfg); }
.cell .t { display: block; font-weight: 700; font-size: var(--fs-0); line-height: 1.25; }
.cell .s { display: block; font-size: var(--fs-0); line-height: 1.3; opacity: .92; }
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
.daylist .dayh { margin: 0 0 var(--space-2); font-size: var(--fs-2); }
.daylist ol { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.daylist li { display: grid; grid-template-columns: 64px 1fr; gap: var(--space-3); align-items: stretch; }
.daylist .when { font-size: var(--fs-0); color: var(--muted); font-variant-numeric: tabular-nums; padding-top: var(--space-2); }
.daylist .when b { display: block; color: var(--ink); }
.daylist .none { color: var(--muted); }
@media (max-width: 760px) {
  table.grid { display: none; }
  .daylist { display: block; }
  h1 { font-size: var(--fs-3); }
  h2 { margin-top: var(--space-6); }
  .nav { margin-left: 0; width: 100%; display: grid; grid-template-columns: repeat(3, 1fr); gap: 0 var(--space-3); }
  .nav a { min-height: 44px; }
}

/* ---- master grid ---- */
.master-tools { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-5); align-items: center; margin: var(--space-3) 0; }
.seg-wrap { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-3); }
.seg-l { font-size: var(--fs-0); font-weight: 600; }
.seg { display: inline-flex; border: 2px solid var(--navy); border-radius: var(--radius); overflow: hidden; }
.seg-opt { position: relative; margin: 0; display: block; font-size: var(--fs-1); font-weight: 600; }
.seg-opt input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }
.seg-opt span { display: flex; align-items: center; min-height: 40px; padding: 0 var(--space-4); background: var(--surface); color: var(--ink); }
.seg-opt + .seg-opt span { border-left: 1px solid var(--navy); }
.seg-opt input:checked + span { background: var(--navy); color: #fff; }
.seg-opt input:checked + span::before { content: "\\2713"; margin-right: 0.4em; }
.seg-opt input:focus-visible + span { outline: 3px solid var(--focus); outline-offset: -4px; }
.seg-opt input:checked:focus-visible + span { outline-color: var(--accent); }
.master-scroll { position: relative; overflow: auto; max-height: min(80vh, 52rem); border: 1px solid var(--line); }
.master-scroll:focus-visible { outline-offset: 0; }
table.master { border-collapse: separate; border-spacing: 0; font-size: 0.8125rem; }
table.master th, table.master td { border: 1px solid var(--line); padding: 0; text-align: center; min-width: 46px; height: 38px; }
table.master thead th { background: var(--surface-2); position: sticky; z-index: 2; padding: 3px 2px; height: 32px; font-size: var(--fs-0); }
table.master thead tr:first-child th { top: 0; }
table.master thead tr:nth-child(2) th { top: 32px; }
table.master th.rowh { position: sticky; left: 0; z-index: 3; background: var(--surface-2); text-align: left; padding: 3px var(--space-2); white-space: nowrap; min-width: 96px; font-size: var(--fs-0); }
table.master thead th.rowh { z-index: 4; }
table.master td.sepl, table.master th.sepl { border-left: 2px solid var(--muted); }
table.master td.dayend, table.master th.dayend { border-right: 2px solid var(--navy); }
table.master td.blocked { color: var(--muted); background: var(--surface-2); }
table.master .mc { position: relative; display: block; height: 100%; padding: 2px; font-weight: 700; line-height: 1.15; background-color: var(--sbg); color: var(--sfg); }
table.master .mc small { display: block; font-weight: 600; font-size: 0.75rem; }
table.master .mc .v1, table.master .mc .v2, table.master .mc .v3 { display: none; }
table.master.view-1 .mc .v1, table.master.view-2 .mc .v2, table.master.view-3 .mc .v3 { display: block; }
.legend { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); list-style: none; padding: 0; margin: var(--space-3) 0; }
.legend li { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--fs-0); }
.swatch { display: inline-block; width: 40px; height: 22px; border-radius: 4px; border-left: 5px solid var(--sbar); background-color: var(--sbg); color: var(--sfg); }

footer { max-width: 1180px; margin: 0 auto; padding: var(--space-4); color: var(--muted); font-size: var(--fs-0); border-top: 1px solid var(--line); display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-1) var(--space-5); }
footer p { margin: 0; }
footer a { display: inline-flex; align-items: center; min-height: 32px; }
footer .tick { color: var(--ok); font-weight: 800; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; scroll-behavior: auto !important; } }

/* ---- print: A4 landscape, ink-friendly ---- */
@page { size: A4 landscape; margin: 10mm; }
@media print {
  :root { color-scheme: light; --bg: #fff; --surface: #fff; --ink: #000; --muted: #333; --line: #888; }
  body { background: #fff; font-size: 10pt; }
  .top, .skip, .nav, .master-tools, .no-print, footer .no-print, .fields, .answer, .hint { display: none !important; }
  main { padding: 0; max-width: none; }
  h1 { font-size: 18pt; }
  .crumbs { display: none; }
  h1 { margin: 0; }
  .facts { border-color: #666; margin: 2mm 0; padding: 1mm 0; }
  table.grid { display: table !important; border-spacing: 1.5px; }
  table.grid td { height: 13mm; }
  table.grid th, table.grid th.period small, table.grid tr.break td { font-size: 9pt; }
  table.grid tr.break td { height: 5mm; padding: 0; }
  table.grid tr { break-inside: avoid; }
  .cell { padding: 1mm 1.5mm; }
  .cell .t { font-size: 9pt; line-height: 1.2; }
  .cell .s { font-size: 8pt; line-height: 1.2; }
  .daylist { display: none !important; }
  .cell { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .scroll, .master-scroll { overflow: visible; max-height: none; border: 0; }
  table.master { font-size: 6.5pt; width: 100%; table-layout: fixed; }
  table.master th, table.master td { min-width: 0; height: 8.2mm; }
  table.master tr { break-inside: avoid; }
  table.master th.rowh { position: static; min-width: 0; width: 24mm; font-size: 7pt; overflow: hidden; }
  table.master thead th { position: static; font-size: 6.5pt; height: auto; }
  table.master .mc small { font-size: 6pt; }
  table.master .mc, .cell, .swatch { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .legend { margin: 2mm 0; break-inside: avoid; }
  .legend li { break-inside: avoid; }
  footer { padding: 2mm 0; }
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
