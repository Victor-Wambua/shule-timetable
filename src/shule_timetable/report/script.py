"""Small progressive-enhancement script: the 'where am I teaching' finder, list filter and
the master-grid view switch. Every page is fully readable without it."""

JS = r"""
(function () {
  'use strict';
  var dataEl = document.getElementById('finder-data');
  var data = null;
  try { data = dataEl ? JSON.parse(dataEl.textContent) : null; } catch (e) { data = null; }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function mins(t) { var x = t.split(':'); return +x[0] * 60 + +x[1]; }

  var form = document.getElementById('finder');
  if (form && data) {
    var who = document.getElementById('f-who');
    var whoLabel = document.getElementById('f-who-l');
    var day = document.getElementById('f-day');
    var per = document.getElementById('f-period');
    var out = document.getElementById('f-answer');
    var kind = document.getElementById('f-kind');
    form.hidden = false;
    var nojs = document.getElementById('f-nojs');
    if (nojs) nojs.hidden = true;
    var hint = document.getElementById('f-hint');
    if (hint) hint.hidden = false;

    function fillWho() {
      var list = kind.value === 'teacher' ? data.teachers : data.classes;
      whoLabel.textContent = kind.value === 'teacher' ? 'Teacher' : 'Class';
      who.innerHTML = list.map(function (t) {
        return '<option value="' + esc(t.id) + '">' + esc(t.name) + '</option>';
      }).join('');
    }
    day.innerHTML = data.days.map(function (d, i) {
      return '<option value="' + i + '">' + esc(d) + '</option>';
    }).join('');
    per.innerHTML = data.periods.map(function (p, i) {
      return '<option value="' + i + '">' + esc(p.label) + ' (' + esc(p.start) + ')</option>';
    }).join('');

    // note: a sentence shown above the answer, e.g. which time "Right now" used
    function answer(note) {
      var table = kind.value === 'teacher' ? data.byTeacher : data.byClass;
      var cell = (table[who.value] || {})[day.value + ',' + per.value];
      var d = data.days[day.value], p = data.periods[per.value];
      var name = who.options[who.selectedIndex].text;
      var when = esc(d) + ' ' + esc(p.label) + ' (' + esc(p.start) + '–' + esc(p.end) + ')';
      var lead = note ? '<span class="assume">' + esc(note) + ' </span>' : '';
      if (+per.value >= data.dayLengths[day.value]) {
        out.innerHTML = lead + esc(d) + ' has no ' + esc(p.label) + '. The school day ends earlier.';
      } else if (data.blocked.indexOf(day.value + ',' + per.value) >= 0) {
        out.innerHTML = lead + 'No lessons run ' + when + '.';
      } else if (!cell) {
        out.innerHTML = lead + '<b>' + esc(name) + '</b> is free ' + when + '. No lesson to go to.';
      } else if (kind.value === 'teacher') {
        out.innerHTML = lead + '<b>' + esc(name) + '</b>, ' + when + ': teach <b>' + esc(cell.subject) +
          '</b> to <b>' + esc(cell.cls) + '</b> in <b>' + esc(cell.room) + '</b>.';
      } else {
        out.innerHTML = lead + '<b>' + esc(name) + '</b>, ' + when + ': <b>' + esc(cell.subject) +
          '</b> with ' + esc(cell.teacher) + ' in <b>' + esc(cell.room) + '</b>.';
      }
    }
    fillWho();
    [kind, who, day, per].forEach(function (el) { el.addEventListener('change', function () {
      if (el === kind) fillWho();
      answer();
    }); });

    // The clock in the school's time zone. Falls back to the device clock if Intl is missing.
    function clock() {
      var now = new Date();
      try {
        var parts = {};
        new Intl.DateTimeFormat('en-GB', {
          timeZone: data.tz, weekday: 'long', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
        }).formatToParts(now).forEach(function (x) { parts[x.type] = x.value; });
        return { weekday: parts.weekday, mins: +parts.hour * 60 + +parts.minute, zone: true };
      } catch (e) {
        var names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        return { weekday: names[now.getDay()], mins: now.getHours() * 60 + now.getMinutes(), zone: false };
      }
    }
    document.getElementById('f-now').addEventListener('click', function () {
      var c = clock();
      var stamp = c.weekday + ' ' + pad(Math.floor(c.mins / 60)) + ':' + pad(c.mins % 60) +
        (c.zone ? ' Nairobi time' : ' on this device');
      var di = data.days.findIndex(function (n) { return n.slice(0, 3).toLowerCase() === c.weekday.slice(0, 3).toLowerCase(); });
      if (di < 0) {
        out.innerHTML = '<span class="assume">Using ' + esc(stamp) + '. </span>The timetable has no ' +
          esc(c.weekday) + ' (it runs ' + esc(data.days[0]) + ' to ' + esc(data.days[data.days.length - 1]) +
          '). Pick a day and period instead.';
        return;
      }
      var last = data.dayLengths[di] - 1;
      var pi = data.periods.findIndex(function (p) { return c.mins >= mins(p.start) && c.mins < mins(p.end); });
      if (pi > last) pi = -1;
      var note = 'Using ' + stamp + '.';
      if (pi < 0) {
        if (c.mins >= mins(data.periods[last].end)) {
          out.innerHTML = '<span class="assume">' + esc(note) + ' </span>Lessons are over for today (the last period ended at ' +
            esc(data.periods[last].end) + '). Pick a day and period instead.';
          return;
        }
        // before school or in a break: show the next period
        pi = data.periods.findIndex(function (p) { return mins(p.start) > c.mins; });
        note += pi === 0 ? ' School has not started; showing the first period.' : ' Between periods; showing the next one.';
      }
      day.value = String(di); per.value = String(pi); answer(note);
    });
    day.value = String(Math.min(3, data.days.length - 1));
    per.value = String(Math.min(2, data.periods.length - 1));
    answer();
  }

  var filter = document.getElementById('dir-filter');
  if (filter) {
    var status = document.getElementById('dir-status');
    var items = document.querySelectorAll('[data-filter]');
    filter.addEventListener('input', function () {
      var q = filter.value.trim().toLowerCase();
      var shown = 0;
      items.forEach(function (li) {
        li.hidden = q !== '' && li.getAttribute('data-filter').indexOf(q) < 0;
        if (!li.hidden) shown += 1;
      });
      document.querySelectorAll('ul.dir').forEach(function (ul) {
        var any = ul.querySelector('li:not([hidden])');
        ul.hidden = !any;
        if (ul.previousElementSibling) ul.previousElementSibling.hidden = !any;
      });
      if (status) {
        status.textContent = q === '' ? '' : shown === 0
          ? 'No page matches "' + filter.value.trim() + '".'
          : shown + (shown === 1 ? ' page matches.' : ' pages match.');
      }
    });
  }

  var tools = document.getElementById('view-tools');
  if (tools) {
    var tbl = document.querySelector('table.master');
    tools.hidden = false;
    tools.querySelectorAll('input[type=radio]').forEach(function (r) {
      r.addEventListener('change', function () {
        if (r.checked) tbl.className = 'master view-' + r.value;
      });
    });
  }
})();
"""
