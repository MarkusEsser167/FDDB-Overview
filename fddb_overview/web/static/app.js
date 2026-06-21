"use strict";

// -------- Hilfsfunktionen --------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const fmt = (v) => (v === null || v === undefined || v === "")
  ? "" : (Math.round(Number(v) * 10) / 10).toLocaleString("de-DE");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

function todayISO() { return new Date().toISOString().slice(0, 10); }

// -------- Tab-Navigation --------
$$("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$("nav button").forEach((b) => b.classList.remove("active"));
    $$(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "help") loadHelp();
  });
});

function gotoTab(name) {
  const btn = $(`nav button[data-tab="${name}"]`);
  if (btn) btn.click();
}

// -------- Übersicht --------
async function loadOverview() {
  try {
    const ov = await api("/api/overview");
    $("#emptyHint").style.display = ov.empty ? "block" : "none";
    if (ov.empty) {
      $("#ovStats").innerHTML = '<div class="muted">Keine Daten.</div>';
      $("#ovInfo").textContent = "";
      return;
    }
    $("#ovInfo").textContent = `${ov.count} Tage  ·  ${ov.first} – ${ov.last}`;
    const t = ov.totals;
    $("#ovStats").innerHTML = `
      ${stat(ov.count, "erfasste Tage")}
      ${stat(fmt(ov.avg_kcal), "Ø kcal / Tag")}
      ${stat(fmt(t.kcal), "kcal gesamt")}
      ${stat(fmt(t.protein) + " g", "Eiweiß gesamt")}
      ${stat(fmt(t.carbs) + " g", "Kohlenhydrate gesamt")}
      ${stat(fmt(t.fat) + " g", "Fett gesamt")}`;
  } catch (e) {
    $("#ovStats").innerHTML = `<div class="error">${esc(e.message)}</div>`;
  }
}
const stat = (v, l) => `<div class="stat"><div class="v">${v}</div><div class="l">${l}</div></div>`;

// -------- Sync --------
async function initSync() {
  try {
    const s = await api("/api/sync/suggest");
    $("#syncFrom").value = s.from;
    $("#syncTo").value = s.to;
  } catch (e) {}
}

$("#syncStart").addEventListener("click", async () => {
  $("#syncStart").disabled = true;
  $("#syncMsg").innerHTML = "";
  try {
    await api("/api/sync/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from: $("#syncFrom").value, to: $("#syncTo").value }),
    });
    pollSync();
  } catch (e) {
    $("#syncMsg").innerHTML = `<span class="error">${esc(e.message)}</span>`;
    $("#syncStart").disabled = false;
  }
});

async function pollSync() {
  try {
    const p = await api("/api/sync/progress");
    const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
    $("#syncProgress").style.width = pct + "%";
    if (p.running) {
      $("#syncMsg").innerHTML = `${esc(p.message)} (${p.done}/${p.total})`;
      setTimeout(pollSync, 600);
    } else {
      $("#syncStart").disabled = false;
      if (p.error) {
        $("#syncMsg").innerHTML = `<span class="error">${esc(p.error)}</span>`;
      } else {
        $("#syncMsg").innerHTML = `<span class="ok">${esc(p.message)}</span>`;
        loadOverview();
      }
    }
  } catch (e) {
    $("#syncStart").disabled = false;
    $("#syncMsg").innerHTML = `<span class="error">${esc(e.message)}</span>`;
  }
}

$("#importBtn").addEventListener("click", async () => {
  const f = $("#importFile").files[0];
  if (!f) { $("#importMsg").textContent = "Bitte Datei wählen."; return; }
  try {
    const text = await f.text();
    const parsed = JSON.parse(text);
    const r = await api("/api/import", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days: parsed }),
    });
    $("#importMsg").innerHTML = `<span class="ok">${r.count} Tage importiert.</span>`;
    loadOverview();
  } catch (e) {
    $("#importMsg").innerHTML = `<span class="error">${esc(e.message)}</span>`;
  }
});

// -------- Tag --------
$("#dayLoad").addEventListener("click", loadDay);
$("#dayExcel").addEventListener("click", () => {
  if ($("#dayDate").value) location.href = `/api/export/excel?date=${$("#dayDate").value}`;
});
$("#dayPdf").addEventListener("click", () => {
  if ($("#dayDate").value) location.href = `/api/export/pdf?date=${$("#dayDate").value}`;
});

async function loadDay() {
  const d = $("#dayDate").value;
  if (!d) return;
  try {
    const day = await api("/api/day/" + d);
    $("#dayResult").innerHTML = renderDay(day, true);
    bindNote(day.date);
    bindProductLinks();
  } catch (e) {
    $("#dayResult").innerHTML = `<div class="card error">${esc(e.message)}</div>`;
  }
}

function renderDay(day, withNote) {
  let rows = "";
  for (const meal of day.meals) {
    rows += `<tr class="meal"><td colspan="3">${esc(meal.name)}</td>
      <td class="num">${fmt(meal.kcal)}</td><td class="num">${fmt(meal.fat)}</td>
      <td class="num">${fmt(meal.carbs)}</td><td class="num">${fmt(meal.protein)}</td></tr>`;
    for (const p of meal.products) {
      const name = p.link
        ? `<a class="plink" data-key="${esc(p.link)}">${esc(p.name)}</a>`
        : esc(p.name);
      rows += `<tr><td></td><td>${esc(p.amount)}</td><td>${name}</td>
        <td class="num">${fmt(p.kcal)}</td><td class="num">${fmt(p.fat)}</td>
        <td class="num">${fmt(p.carbs)}</td><td class="num">${fmt(p.protein)}</td></tr>`;
    }
  }
  const t = day.totals;
  rows += `<tr class="total"><td colspan="3">Tagessumme</td>
    <td class="num">${fmt(t.kcal)}</td><td class="num">${fmt(t.fat)}</td>
    <td class="num">${fmt(t.carbs)}</td><td class="num">${fmt(t.protein)}</td></tr>`;
  const extra = [];
  if (t.sugar != null) extra.push(`davon Zucker: ${fmt(t.sugar)} g`);
  if (t.fiber != null) extra.push(`Ballaststoffe: ${fmt(t.fiber)} g`);

  const note = withNote ? `
    <div style="margin-top:12px">
      <label>Besonderheiten an diesem Tag</label>
      <textarea id="noteBox">${esc(day.note || "")}</textarea>
      <button class="btn secondary" id="noteSave" style="margin-top:6px">Notiz speichern</button>
      <span id="noteMsg" class="muted"></span>
    </div>` : "";

  return `<div class="card">
    <h2>${esc(day.weekday)}, ${esc(day.date)} ${day.complete ? "" : '<span class="pill">unvollständig</span>'}</h2>
    <table>
      <thead><tr><th></th><th>Menge</th><th>Produkt</th>
        <th class="num">kcal</th><th class="num">Fett</th>
        <th class="num">KH</th><th class="num">Eiweiß</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${extra.length ? `<p class="muted">${extra.join(" &nbsp; ")}</p>` : ""}
    ${note}
    <details style="margin-top:10px"><summary class="muted">Text zum Kopieren</summary>
      <textarea class="copybox" readonly>${esc(day.copy_text)}</textarea></details>
  </div>`;
}

function bindNote(date) {
  const btn = $("#noteSave");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    try {
      await api("/api/note", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, text: $("#noteBox").value }),
      });
      $("#noteMsg").innerHTML = '<span class="ok">gespeichert</span>';
    } catch (e) { $("#noteMsg").innerHTML = `<span class="error">${esc(e.message)}</span>`; }
  });
}

function bindProductLinks() {
  $$("a.plink").forEach((a) => a.addEventListener("click", () => {
    openProduct(a.dataset.key);
  }));
}

// -------- Datumsbereich --------
$("#rangeLoad").addEventListener("click", loadRange);
$("#rangeExcel").addEventListener("click", () => exportRange("excel"));
$("#rangePdf").addEventListener("click", () => exportRange("pdf"));
function exportRange(kind) {
  const f = $("#rangeFrom").value, t = $("#rangeTo").value;
  if (f && t) location.href = `/api/export/${kind}?date_from=${f}&date_to=${t}`;
}

async function loadRange() {
  const f = $("#rangeFrom").value, t = $("#rangeTo").value;
  if (!f || !t) return;
  try {
    const r = await api(`/api/range?date_from=${f}&date_to=${t}`);
    let html = `<div class="card"><h2>${r.from} – ${r.to} (${r.count} Tage)</h2>
      <div class="stat-grid">
        ${stat(fmt(r.totals.kcal), "kcal gesamt")}
        ${stat(fmt(r.averages.kcal), "Ø kcal / Tag")}
        ${stat(fmt(r.averages.protein) + " g", "Ø Eiweiß")}
        ${stat(fmt(r.averages.carbs) + " g", "Ø KH")}
        ${stat(fmt(r.averages.fat) + " g", "Ø Fett")}
      </div>
      <div class="row" style="margin-top:12px">
        <details style="flex:1"><summary class="muted">Tagestexte kopieren</summary>
          <textarea class="copybox" readonly>${esc(r.day_copy_text)}</textarea></details>
        <details style="flex:1"><summary class="muted">Mahlzeitentexte kopieren</summary>
          <textarea class="copybox" readonly>${esc(r.meal_copy_text)}</textarea></details>
      </div></div>`;
    for (const day of r.days) html += renderDay(day, false);
    $("#rangeResult").innerHTML = html;
    bindProductLinks();
  } catch (e) {
    $("#rangeResult").innerHTML = `<div class="card error">${esc(e.message)}</div>`;
  }
}

// -------- Listen --------
let weekdaySel = new Set();
const WD = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
function renderWeekdayFilter() {
  $("#weekdayFilter").innerHTML = "Wochentage: " + WD.map((w, i) =>
    `<label style="display:inline-block;margin-right:8px"><input type="checkbox" style="width:auto" data-wd="${i}"
      ${weekdaySel.has(i) ? "checked" : ""}> ${w}</label>`).join("");
  $$('#weekdayFilter input[data-wd]').forEach((c) => c.addEventListener("change", () => {
    const i = Number(c.dataset.wd);
    c.checked ? weekdaySel.add(i) : weekdaySel.delete(i);
  }));
}

$("#searchBtn").addEventListener("click", async () => {
  const wd = Array.from(weekdaySel).join(",");
  const data = await api(`/api/list/search?q=${encodeURIComponent($("#searchQ").value)}&weekdays=${wd}`);
  renderProductList(data, "Suchergebnis");
});
$("#topBtn").addEventListener("click", async () => {
  renderProductList(await api("/api/list/top?limit=100"), "Top 100 Lebensmittel");
});
$("#rankBtn").addEventListener("click", async () => {
  const m = $("#rankMetric").value;
  const data = await api(`/api/list/ranking?metric=${m}&limit=100`);
  let rows = data.map((r, i) => `<tr><td>${i + 1}</td>
    <td><a class="plink" data-day="${esc(r.date)}">${esc(r.date)}</a></td>
    <td>${esc(r.weekday)}</td><td class="num">${fmt(r.value)}</td>
    <td class="num">${fmt(r.kcal)}</td></tr>`).join("");
  $("#listResult").innerHTML = `<div class="card"><h2>Tagesranking (${esc(m)})</h2>
    <table><thead><tr><th>#</th><th>Datum</th><th>Wochentag</th>
      <th class="num">Wert</th><th class="num">kcal</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  bindDayLinks();
});

function renderProductList(items, title) {
  if (!items.length) { $("#listResult").innerHTML = `<div class="card muted">Keine Treffer.</div>`; return; }
  let rows = items.map((p, i) => `<tr><td>${i + 1}</td>
    <td><a class="plink" data-key="${esc(p.link || p.name)}">${esc(p.name)}</a></td>
    <td class="num">${p.count}</td><td class="num">${fmt(p.total_kcal)}</td></tr>`).join("");
  $("#listResult").innerHTML = `<div class="card"><h2>${esc(title)}</h2>
    <table><thead><tr><th>#</th><th>Produkt</th>
      <th class="num">Tage</th><th class="num">kcal gesamt</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  $$('#listResult a.plink').forEach((a) => a.addEventListener("click", () => openProduct(a.dataset.key)));
}

function bindDayLinks() {
  $$('#listResult a.plink[data-day]').forEach((a) => a.addEventListener("click", () => {
    gotoTab("day"); $("#dayDate").value = a.dataset.day; loadDay();
  }));
}

async function openProduct(key) {
  try {
    const r = await api("/api/list/product?key=" + encodeURIComponent(key));
    let rows = r.entries.map((e) => `<tr>
      <td><a class="plink" data-day="${esc(e.date)}">${esc(e.date)}</a></td>
      <td>${esc(e.meal)}</td><td>${esc(e.amount)}</td>
      <td class="num">${fmt(e.kcal)}</td></tr>`).join("");
    $("#listResult").innerHTML = `<div class="card"><h2>Verzehrtage: ${esc(r.query)}</h2>
      <p class="muted">${r.count} Einträge</p>
      <table><thead><tr><th>Datum</th><th>Mahlzeit</th><th>Menge</th>
        <th class="num">kcal</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    bindDayLinks();
  } catch (e) {
    $("#listResult").innerHTML = `<div class="card error">${esc(e.message)}</div>`;
  }
}

// -------- Verdichtungen --------
$$('button[data-agg]').forEach((b) => b.addEventListener("click", async () => {
  const kind = b.dataset.agg;
  const titles = { meal: "Nach Mahlzeit", weekday: "Nach Wochentag", month: "Nach Monat" };
  try {
    const data = await api("/api/aggregate/" + kind);
    let rows = data.map((g) => `<tr><td>${esc(g.label)}</td><td class="num">${g.count}</td>
      <td class="num">${fmt(g.kcal_avg)}</td><td class="num">${fmt(g.kcal_sum)}</td>
      <td class="num">${fmt(g.fat_avg)}</td><td class="num">${fmt(g.carbs_avg)}</td>
      <td class="num">${fmt(g.protein_avg)}</td></tr>`).join("");
    $("#aggResult").innerHTML = `<div class="card"><h2>${titles[kind]}</h2>
      <table><thead><tr><th>Gruppe</th><th class="num">n</th>
        <th class="num">Ø kcal</th><th class="num">kcal Σ</th>
        <th class="num">Ø Fett</th><th class="num">Ø KH</th>
        <th class="num">Ø Eiweiß</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  } catch (e) {
    $("#aggResult").innerHTML = `<div class="card error">${esc(e.message)}</div>`;
  }
}));

// -------- Einstellungen --------
async function loadSettings() {
  const s = await api("/api/settings");
  $("#setName").value = s.name || "";
  $("#setBirth").value = s.birthdate || "";
  $("#setUser").value = s.fddb_username || "";
  $("#pwState").textContent = s.has_password ? "(gesetzt)" : "";
  $("#ckState").textContent = s.has_cookie ? "(gesetzt)" : "";
}
$("#setSave").addEventListener("click", async () => {
  try {
    await api("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("#setName").value, birthdate: $("#setBirth").value,
        fddb_username: $("#setUser").value, fddb_password: $("#setPass").value,
        fddb_cookie: $("#setCookie").value,
      }),
    });
    $("#setMsg").innerHTML = '<span class="ok">gespeichert</span>';
    $("#setPass").value = "";
    loadSettings();
  } catch (e) { $("#setMsg").innerHTML = `<span class="error">${esc(e.message)}</span>`; }
});

// -------- Hilfe --------
async function loadHelp() {
  try {
    const res = await fetch("/help");
    $("#helpContent").innerHTML = await res.text();
  } catch (e) { $("#helpContent").textContent = "Hilfe nicht verfügbar."; }
}

// -------- Init --------
function init() {
  const t = todayISO();
  ["dayDate", "rangeFrom", "rangeTo"].forEach((id) => { if ($("#" + id)) $("#" + id).value = t; });
  renderWeekdayFilter();
  loadOverview();
  initSync();
  loadSettings();
}
init();
