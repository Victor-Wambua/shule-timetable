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

  var form = document.getElementById('finder');
  if (form && data) {
    var who = document.getElementById('f-who');
    var day = document.getElementById('f-day');
    var per = document.getElementById('f-period');
    var out = document.getElementById('f-answer');
    var kind = document.getElementById('f-kind');

    function fillWho() {
      var list = kind.value === 'teacher' ? data.teachers : data.classes;
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

    function answer() {
      var table = kind.value === 'teacher' ? data.byTeacher : data.byClass;
      var cell = (table[who.value] || {})[day.value + ',' + per.value];
      var d = data.days[day.value], p = data.periods[per.value];
      var name = who.options[who.selectedIndex].text;
      var when = esc(d) + ' ' + esc(p.label) + ' (' + esc(p.start) + '–' + esc(p.end) + ')';
      if (+per.value >= data.dayLengths[day.value]) {
        out.innerHTML = esc(d) + ' has no ' + esc(p.label) + '. The school day ends earlier.';
      } else if (data.blocked.indexOf(day.value + ',' + per.value) >= 0) {
        out.innerHTML = 'No lessons run ' + when + '.';
      } else if (!cell) {
        out.innerHTML = '<b>' + esc(name) + '</b> is free ' + when + '.';
      } else if (kind.value === 'teacher') {
        out.innerHTML = '<b>' + esc(name) + '</b>, ' + when + ': teach <b>' + esc(cell.subject) +
          '</b> to <b>' + esc(cell.cls) + '</b> in <b>' + esc(cell.room) + '</b>.';
      } else {
        out.innerHTML = '<b>' + esc(name) + '</b>, ' + when + ': <b>' + esc(cell.subject) +
          '</b> with ' + esc(cell.teacher) + ' in <b>' + esc(cell.room) + '</b>.';
      }
    }
    fillWho();
    [kind, who, day, per].forEach(function (el) { el.addEventListener('change', function () {
      if (el === kind) fillWho();
      answer();
    }); });
    document.getElementById('f-now').addEventListener('click', function () {
      var now = new Date();
      var names = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
      var today = names[now.getDay()];
      var di = data.days.findIndex(function (n) { return n.slice(0, 3).toLowerCase() === today; });
      var mins = now.getHours() * 60 + now.getMinutes();
      function m(t) { var x = t.split(':'); return +x[0] * 60 + +x[1]; }
      var pi = data.periods.findIndex(function (p) { return mins >= m(p.start) && mins < m(p.end); });
      if (di < 0 || pi < 0) {
        out.textContent = 'No lesson is running right now. Pick a day and period instead.';
        return;
      }
      day.value = String(di); per.value = String(pi); answer();
    });
    day.value = String(Math.min(3, data.days.length - 1));
    per.value = String(Math.min(2, data.periods.length - 1));
    answer();
  }

  var filter = document.getElementById('dir-filter');
  if (filter) {
    filter.addEventListener('input', function () {
      var q = filter.value.trim().toLowerCase();
      document.querySelectorAll('[data-filter]').forEach(function (li) {
        li.hidden = q !== '' && li.getAttribute('data-filter').indexOf(q) < 0;
      });
    });
  }

  var tools = document.getElementById('view-tools');
  if (tools) {
    var tbl = document.querySelector('table.master');
    tools.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        tbl.className = 'master view-' + b.getAttribute('data-view');
        tools.querySelectorAll('button').forEach(function (x) {
          x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
        });
      });
    });
  }
})();
"""
