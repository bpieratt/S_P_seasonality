/* S&P 500 Seasonality dashboard — rendering only. All numbers come from DATA,
   which build_data.py derives from the research files and cross-checks. */
(function () {
"use strict";
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const rnd = (v, nd) => +(v * 100).toFixed(nd);   // rounded percent; avoids "−0.0%"
const pct = (v, nd = 2, sign = true) => { if (v == null || isNaN(v)) return '<span class="na">n/a</span>'; const r = rnd(v, nd);
  if (!sign) return `${Math.abs(r).toFixed(nd)}%`;
  return `<span class="${r > 0 ? "pos" : r < 0 ? "neg" : ""}">${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(nd)}%</span>`; };
const pctPlain = (v, nd = 2) => { const r = rnd(v, nd); return (r > 0 ? "+" : r < 0 ? "−" : "") + Math.abs(r).toFixed(nd) + "%"; };
const ppts = (v, nd = 2) => { if (v == null) return '<span class="na">n/a</span>'; const r = rnd(v, nd);
  return `<span class="${r > 0 ? "pos" : r < 0 ? "neg" : ""}">${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(nd)} pts</span>`; };
const share = v => v == null ? '<span class="na">n/a</span>' : Math.round(v * 100) + "%";
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const mdLabel = md => MON[+md.slice(0, 2) - 1] + " " + (+md.slice(3));
const ruleLabel = p => `${mdLabel(p.start)} → ${mdLabel(p.end)}`;

/* ---------------------------------------------------------------- term tooltips */
const TERMS = {};
GLOSSARY.terms.forEach(t => TERMS[t.id] = { title: t.term, body: t.meaning, why: t.why, anchor: "g-" + t.id });
GLOSSARY.formulas.forEach(f => TERMS[f.id] = { title: f.name, body: f.formula, why: f.reading, anchor: "f-" + f.id, mono: true });
const info = id => TERMS[id] ? `<button type="button" class="info" data-term="${id}" aria-label="Explain: ${esc(TERMS[id].title)}" aria-expanded="false">i</button>` : "";
let pop = null, popBtn = null, pinned = false;
function closePop() { if (pop) pop.remove(); if (popBtn) popBtn.setAttribute("aria-expanded", "false"); pop = popBtn = null; pinned = false; }
function openPop(btn, pin) {
  if (popBtn === btn) { pinned = pinned || pin; return; }
  closePop();
  const t = TERMS[btn.dataset.term]; if (!t) return;
  pop = document.createElement("div"); pop.className = "pop"; pop.setAttribute("role", "tooltip"); pop.id = "pop-" + btn.dataset.term;
  pop.innerHTML = `<div class="pt">${esc(t.title)}</div><div${t.mono ? ' class="formula"' : ""}>${esc(t.body)}</div><div class="pw">${esc(t.why)}</div><a href="#${t.anchor}">Full explanation in the glossary →</a>`;
  document.body.appendChild(pop);
  const r = btn.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
  let left = window.scrollX + r.left + r.width / 2 - w / 2;
  left = Math.max(window.scrollX + 8, Math.min(left, window.scrollX + document.documentElement.clientWidth - w - 8));
  let top = window.scrollY + r.bottom + 8;
  if (r.bottom + h + 16 > window.innerHeight && r.top > h + 16) top = window.scrollY + r.top - h - 8;
  pop.style.left = left + "px"; pop.style.top = top + "px";
  btn.setAttribute("aria-expanded", "true"); btn.setAttribute("aria-describedby", pop.id);
  popBtn = btn; pinned = !!pin;
  pop.querySelector("a").addEventListener("click", closePop);
}
const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
document.addEventListener("click", e => {
  const b = e.target.closest("button.info");
  if (b) { e.preventDefault(); e.stopPropagation(); if (popBtn === b && pinned) closePop(); else openPop(b, true); return; }
  if (pop && !e.target.closest(".pop")) closePop();
});
if (finePointer) {
  document.addEventListener("mouseover", e => { const b = e.target.closest("button.info"); if (b && !pinned) openPop(b, false); });
  document.addEventListener("mouseout", e => { const b = e.target.closest("button.info"); if (b && !pinned && !(e.relatedTarget && e.relatedTarget.closest(".pop"))) closePop(); });
}
document.addEventListener("focusin", e => { const b = e.target.closest("button.info"); if (b && !pinned) openPop(b, false); });
document.addEventListener("keydown", e => { if (e.key === "Escape" && pop) { const b = popBtn; closePop(); b && b.focus(); } });
window.addEventListener("resize", closePop);

/* ---------------------------------------------------------------- chart hover tips */
function chartTip(container) {
  if (container._tip) { if (!container.contains(container._tip.el)) container.appendChild(container._tip.el); return container._tip; }
  const t = document.createElement("div"); t.className = "tip"; t.hidden = true; container.appendChild(t);
  const show = (e, html) => { t.innerHTML = html; t.hidden = false; const r = container.getBoundingClientRect();
    let l = e.clientX - r.left + 12; if (l > r.width - 210) l = Math.max(4, l - 230); t.style.left = l + "px"; t.style.top = (e.clientY - r.top + 14) + "px"; };
  container.addEventListener("pointermove", e => { const h = e.target.closest("[data-t]"); h ? show(e, h.dataset.t) : (t.hidden = true); });
  container.addEventListener("pointerleave", () => t.hidden = true);
  return (container._tip = { show, hide: () => t.hidden = true, el: t });
}
function ticks(lo, hi, n) { const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw); const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-12; v += step) out.push(+v.toFixed(10)); return out; }
const TXT = 'font-family="inherit" fill="var(--text-dim)" font-size="11"';

/* ---------------------------------------------------------------- sortable table */
function table(el, cols, rows, opt = {}) {
  let sortKey = opt.sortKey || null, dir = opt.dir || 1;
  function draw() {
    let rs = rows.slice();
    if (sortKey != null) { const c = cols.find(c => c.key === sortKey); const f = c.sort || (r => r[c.key]);
      rs.sort((a, b) => { const x = f(a), y = f(b); if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * dir; }); }
    const head = cols.map(c => `<th scope="col" class="${c.l ? "l " : ""}${opt.sortable !== false && c.sortable !== false ? "sortable" : ""}" data-k="${c.key}" ${opt.sortable !== false && c.sortable !== false ? `tabindex="0" aria-sort="${sortKey === c.key ? (dir > 0 ? "ascending" : "descending") : "none"}"` : ""}>${c.label}${c.info ? info(c.info) : ""}${sortKey === c.key ? `<span class="arrow">${dir > 0 ? "▲" : "▼"}</span>` : ""}</th>`).join("");
    const body = rs.map((r, i) => {
      const tr = `<tr${opt.rowAttr ? opt.rowAttr(r, i) : ""}>` + cols.map(c => `<td class="${c.l ? "l " : ""}${c.cls || ""}">${c.fmt ? c.fmt(r) : esc(r[c.key])}</td>`).join("") + "</tr>";
      return tr + (opt.detail ? opt.detail(r, cols.length) : "");
    }).join("");
    el.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body}</tbody>`;
    $$("th.sortable", el).forEach(th => {
      const go = e => { if (e.target.closest("button.info")) return; const k = th.dataset.k; if (sortKey === k) dir = -dir; else { sortKey = k; dir = -1; } draw(); el.querySelector(`th[data-k="${k}"]`).focus(); };
      th.addEventListener("click", go); th.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(e); } });
    });
    if (opt.after) opt.after(el);
  }
  draw();
  return { setRows(r) { rows = r; draw(); } };
}

/* ---------------------------------------------------------------- badges */
const IS_BADGE = { "Strong Historical Evidence": ["ev-supp", "Strong"], "Moderate Historical Evidence": ["ev-hist", "Moderate*"],
  "Weak / Inconclusive": ["ev-inc", "Weak"], "No Meaningful Seasonal Effect": ["ev-none", "None"] };
const OOS_BADGE = { "SUPPORTIVE": ["ev-supp", "Supportive"], "PARTIALLY SUPPORTIVE": ["ev-part", "Partly supportive"],
  "INCONCLUSIVE": ["ev-inc", "Inconclusive"], "INCONCLUSIVE (N<3)": ["ev-inc", "Inconclusive"], "CONTRADICTED": ["ev-contra", "Contradicted"] };
const badge = (map, k) => { const b = map[k] || ["ev-none", k]; return `<span class="badge ${b[0]}">${b[1]}</span>`; };
const dirTxt = d => d === "bullish" ? '<span class="pos">▲ bullish</span>' : '<span class="neg">▼ bearish</span>';

/* ================================================================ B. months chart */
const M = DATA.months;
function monthsChart(view) {
  const el = $("#ch-months"), W = 860, H = 280, m = { l: 46, r: 10, t: 12, b: 30 };
  const series = view === "hist" ? [["is_", "var(--series-hist)", "2003–2022 average"]] : view === "recent" ? [["oos", "var(--series-recent)", "2023–2026 average"]]
    : [["is_", "var(--series-hist)", "2003–2022 average"], ["oos", "var(--series-recent)", "2023–2026 average"]];
  const vals = series.flatMap(s => M[s[0]].map(r => r.avg)).concat([0]);
  const lo = Math.min(...vals) * 1.15 - 0.002, hi = Math.max(...vals) * 1.1 + 0.002;
  const Y = v => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b), gw = (W - m.l - m.r) / 12, bw = Math.min(30, (gw - 10) / series.length);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Average return by calendar month">`;
  ticks(lo, hi, 5).forEach(v => s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--border)"/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end" ${TXT}>${(v * 100).toFixed(1)}%</text>`);
  s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--text-dim)"/>`;
  if (view !== "recent") s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(M.is_avg_all)}" y2="${Y(M.is_avg_all)}" stroke="var(--series-hist)" stroke-dasharray="4 4" opacity=".8"/>`;
  if (view !== "hist") s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(M.oos_avg_all)}" y2="${Y(M.oos_avg_all)}" stroke="var(--series-recent)" stroke-dasharray="4 4" opacity=".8"/>`;
  MON.forEach((mo, i) => {
    const cx = m.l + gw * i + gw / 2, x0 = cx - bw * series.length / 2;
    series.forEach(([k, c, lab], j) => { const r = M[k][i], v = r.avg, y0 = Math.min(Y(0), Y(v)), h = Math.max(1, Math.abs(Y(v) - Y(0)));
      s += `<rect x="${x0 + j * bw + 1}" y="${y0}" width="${bw - 2}" height="${h}" rx="3" fill="${c}" data-t="<b>${mo} · ${lab}</b><br>Average ${pctPlain(v)} · median ${pctPlain(r.median)}<br>Up in ${r.pos} of ${r.n} years"/>`; });
    s += `<text x="${cx}" y="${H - 9}" text-anchor="middle" ${TXT}>${mo}</text>`;
  });
  el.innerHTML = s + "</svg>"; chartTip(el);
  $("#lg-months").innerHTML = series.map(([, c, lab]) => `<span><i style="background:${c}"></i>${lab}</span>`).join("")
    + (view !== "recent" ? `<span><i class="dash" style="border-color:var(--series-hist)"></i>typical month 2003–22 (${pctPlain(M.is_avg_all)})</span>` : "")
    + (view !== "hist" ? `<span><i class="dash" style="border-color:var(--series-recent)"></i>typical month 2023–26 (${pctPlain(M.oos_avg_all)})</span>` : "");
  const top = (k, n, asc) => M[k].map((r, i) => [MON[i], r.avg]).sort((a, b) => asc ? a[1] - b[1] : b[1] - a[1]).slice(0, n).map(x => `${x[0]} (${pctPlain(x[1])})`).join(", ");
  const tell = {
    hist: `The strongest months on average were ${top("is_", 3)}; the weakest were ${top("is_", 3, true)}. These gaps are small next to the normal month-to-month swing of about ±${(DATA.compare.is_.std * 100).toFixed(1)}%, and none of them passed the statistical test.`,
    recent: `In 2023–2026 the strongest months were ${top("oos", 3)}, and the weakest were ${top("oos", 2, true)}. Each bar averages only 3–4 months, so one big month can dominate it. April 2026 alone was +10.4%.`,
    both: `Where the two bars point the same way at similar heights, the historical tendency held. Most months don't line up: the rank correlation between the two monthly patterns is only ${DATA.compare.consistency.rank_corr_month_pattern.toFixed(2)} (1 would mean the same pattern, 0 no relationship).`
  }[view];
  $("#tell-months").innerHTML = `<div class="t">What does this chart tell me?</div>${tell}<div class="caution">Caution: 2003–2022 bars average 20 years each; 2023–2026 bars average only 3–4.</div>`;
}

/* ================================================================ B. months tables */
function monthTables() {
  const rows = M.is_.map(r => r);
  table($("#tbl-months"), [
    { key: "m", label: "Month", l: true, sort: r => MON.indexOf(r.m), fmt: r => `<b>${r.m}</b>` },
    { key: "avg", label: "Average", info: "avg", fmt: r => pct(r.avg) },
    { key: "median", label: "Median", info: "median", fmt: r => pct(r.median) },
    { key: "pos", label: "Up years", fmt: r => `<span class="pos">${r.pos}</span>` },
    { key: "neg", label: "Down years", fmt: r => `<span class="neg">${r.neg}</span>` },
    { key: "pct_pos", label: "% years up", info: "winrate", fmt: r => `${share(r.pct_pos)}<span class="bar-track"><span class="bar-fill" style="width:${r.pct_pos * 100}%"></span></span>` },
    { key: "best", label: "Best year", fmt: r => pct(r.best) },
    { key: "worst", label: "Worst year", fmt: r => pct(r.worst) },
    { key: "worst_mdd", label: "Worst dip", info: "mdd", fmt: r => pct(r.worst_mdd) },
    { key: "excess", label: "vs typical month", info: "excess", fmt: r => ppts(r.excess) },
    { key: "frozen_class", label: "Evidence", info: "significance", l: true, sort: r => ({ "Weak / Inconclusive": 1, "No Meaningful Seasonal Effect": 0 })[r.frozen_class], fmt: r => badge(IS_BADGE, r.frozen_class) },
  ], rows, { sortKey: "m", dir: 1 });
  table($("#tbl-months-tech"), [
    { key: "m", label: "Month", l: true, sort: r => MON.indexOf(r.m) },
    { key: "excess", label: "Excess vs typical", info: "excess", fmt: r => ppts(r.excess) },
    { key: "std", label: "Std deviation", info: "sd", fmt: r => pct(r.std, 2, false) },
    { key: "t", label: "t-statistic", info: "tstat", fmt: r => r.t.toFixed(2) },
    { key: "p_t", label: "p-value (t-test)", info: "pvalue", fmt: r => r.p_t.toFixed(3) },
    { key: "p_w", label: "p-value (Wilcoxon)", fmt: r => r.p_w.toFixed(3) },
    { key: "q", label: "q-value (FDR)", info: "qvalue", fmt: r => r.q.toFixed(2) },
  ], rows, { sortKey: "m", dir: 1 });
}

function windowsHist() {
  const rows = DATA.primaries;
  table($("#tbl-windows-hist"), [
    { key: "rank", label: "Rank", fmt: r => r.rank },
    { key: "start", label: "Window", l: true, info: "window", fmt: r => `<b>${ruleLabel(r)}</b> <span class="dim">· ${r.days} td</span>` },
    { key: "dir", label: "Direction", l: true, fmt: r => dirTxt(r.dir) },
    { key: "is_hit", label: "Right way", info: "winrate", fmt: r => share(r.is_hit) },
    { key: "is_mean", label: "Average", info: "avg", fmt: r => pct(r.is_mean) },
    { key: "is_median", label: "Median", info: "median", fmt: r => pct(r.is_median) },
    { key: "is_excess", label: "vs ordinary period", info: "excess", fmt: r => ppts(r.is_excess) },
    { key: "is_worst_mdd", label: "Worst dip", info: "mdd", fmt: r => pct(r.is_worst_mdd) },
    { key: "is_p", label: "p-value", info: "pvalue", fmt: r => r.is_p.toFixed(3) },
    { key: "is_q", label: "q-value", info: "qvalue", fmt: r => r.is_q.toFixed(2) },
    { key: "is_class", label: "Evidence", l: true, sortable: false, fmt: r => badge(IS_BADGE, r.is_class) },
  ], rows, { sortKey: "rank", dir: 1 });
}

/* ================================================================ C/D heat maps */
const CAP = 0.08, FLAT = 0.005;
function heatStyle(r) {
  if (Math.abs(r) < FLAT) return `background:var(--heat-zero);color:var(--text)`;
  const t = Math.min(Math.abs(r) / CAP, 1), base = r > 0 ? css("--accent") : css("--fail");
  const pctMix = Math.round(22 + 78 * t);
  return `background:color-mix(in srgb, ${base} ${pctMix}%, #232939);color:${t > 0.55 ? "#10141F" : "var(--text)"}`;
}
function heatTable(el, grid, avgs, label, ns) {
  let h = `<table class="heat"><thead><tr><th class="rowh" scope="col">Year</th>${MON.map(m => `<th scope="col">${m}</th>`).join("")}<th scope="col">Year</th></tr></thead><tbody>`;
  grid.forEach(row => {
    h += `<tr><th class="rowh" scope="row">${row.year}</th>`;
    row.cells.forEach((c, i) => {
      if (c.state === "complete") h += `<td style="${heatStyle(c.ret)}" data-t="<b>${MON[i]} ${row.year}</b><br>Return ${pctPlain(c.ret)}<br>Deepest dip in month ${pctPlain(c.mdd)}">${pctPlain(c.ret, 1)}</td>`;
      else if (c.state === "recent") h += `<td class="recent" style="${heatStyle(c.ret)}" data-t="<b>${MON[i]} ${row.year}: recent, unlocked</b><br>Return ${pctPlain(c.ret)}<br>Deepest dip in month ${pctPlain(c.mdd)}<br><i>After the locked validation date — descriptive only, excluded from every statistic on this page.</i>">${pctPlain(c.ret, 1)}</td>`;
      else if (c.state === "partial") h += `<td class="partial" data-t="<b>${MON[i]} ${row.year}: in progress</b><br>Data runs only through ${c.through}.<br>No monthly return is calculated.">In progress</td>`;
      else h += `<td class="future" data-t="<b>${MON[i]} ${row.year}</b><br>Not yet happened">—</td>`;
    });
    const yr = row.year_ret;
    h += row.full_year ? `<td class="year ${yr > 0 ? "pos" : "neg"}" data-t="<b>${row.year} full year</b><br>${pctPlain(yr)}">${pctPlain(yr, 1)}</td>`
      : `<td class="year" style="color:var(--highlight)" data-t="<b>${row.year}, Jan–${MON[row.months_in_year - 1]} only</b><br>${pctPlain(yr)} over ${row.months_in_year} completed months.<br>Not a full-year return.">${pctPlain(yr, 1)}<br><span style="font-size:10px;font-weight:400">Jan–${MON[row.months_in_year - 1]}</span></td>`;
    h += "</tr>";
  });
  h += `<tr class="avg"><th class="rowh" scope="row">Average</th>${avgs.map((v, i) => `<td class="${v > 0 ? "pos" : "neg"}" data-t="<b>${MON[i]} average</b><br>${pctPlain(v)} over ${ns ? ns[i] : 20} years">${pctPlain(v, 1)}</td>`).join("")}<td></td></tr>`;
  el.innerHTML = h + "</tbody></table>";
  el.insertAdjacentHTML("afterend", `<p class="caution">${label}</p>`);
  chartTip(el.closest(".panel-b"));
}
function heatLegend(el) {
  const bins = [-0.08, -0.06, -0.04, -0.02, 0, 0.02, 0.04, 0.06, 0.08];
  el.innerHTML = `<span>Monthly return:</span><span class="legend-scale">${bins.map(b => `<span style="${heatStyle(b === 0 ? 0 : b)}">${b === 0 ? "≈0" : (b > 0 ? "+" : "−") + Math.abs(b * 100) + "%"}${Math.abs(b) === CAP ? (b > 0 ? "+" : "") : ""}</span>`).join("")}</span>
    <span><span class="swatch" style="background:var(--heat-zero)"></span>between −0.5% and +0.5%</span>
    <span><span class="swatch" style="background:repeating-linear-gradient(135deg, rgba(245,182,66,0.3) 0 4px, rgba(245,182,66,0.08) 4px 8px);outline:1px dashed #6b5424"></span>In progress (excluded)</span>
    <span><span class="swatch recent-swatch" style="background:var(--heat-zero);outline:2px dashed var(--highlight)"></span>Recent, after the lock (informal — excluded from every statistic)</span>
    <span><span class="swatch" style="outline:1px dashed var(--border)"></span>Not yet happened</span>`;
}
function recentDataNote() {
  const m = DATA.meta;
  if (!m.recent_available) return;
  const panel = document.querySelector("#heat-new .panel-h .desc");
  if (!panel) return;
  panel.insertAdjacentHTML("beforeend",
    ` <b>Updated since the lock:</b> months through ${m.oos_last_recent} are also shown (dashed outline), refreshed monthly. ` +
    `They are not part of the locked validation above and are never used in any statistic, p-value or verdict on this page — ` +
    `shown for interest only, the same way the "In progress" cell was before it completed.`);
}

/* ================================================================ C2. day-by-day calendar heat map */
function calendarHeat() {
  const H = DATA.calendar_heat, CAPC = 0.015, FLATC = 0.001, grid = $("#cal-grid");
  const col = v => { if (Math.abs(v) < FLATC) return "var(--heat-zero)"; const t = Math.min(Math.abs(v) / CAPC, 1);
    return `color-mix(in srgb, ${v > 0 ? css("--accent") : css("--fail")} ${Math.round(18 + 82 * t)}%, #232939)`; };
  const by = {}; H.cells.forEach(c => by[c.m + "-" + c.d] = c);
  let h = `<div></div>` + Array.from({ length: 31 }, (_, i) => `<div class="dl">${(i + 1) % 5 === 1 || i === 30 ? i + 1 : ""}</div>`).join("");
  for (let m = 1; m <= 12; m++) {
    h += `<div class="ml">${MON[m - 1]}</div>`;
    for (let d = 1; d <= 31; d++) { const c = by[m + "-" + d];
      h += c ? `<div class="c" tabindex="0" style="background:${col(c.ex)}" aria-label="${MON[m - 1]} ${d}: next 5 trading days ${pctPlain(c.ex)} versus normal, up in ${Math.round(c.pp * 100)}% of years" data-t="<b>${MON[m - 1]} ${d}</b><br>Next 5 trading days vs normal: ${ppts(c.ex).replace(/<[^>]+>/g, "")}<br>Market up over those 5 days in ${Math.round(c.pp * 100)}% of years (${c.n} yrs)"></div>` : `<div class="c none"></div>`; }
  }
  grid.innerHTML = h;
  const tip = chartTip(grid.closest(".panel-b"));
  grid.addEventListener("focusin", e => { const c = e.target.closest("[data-t]"); if (c) { const r = c.getBoundingClientRect(); tip.show({ clientX: r.right, clientY: r.top }, c.dataset.t); } });
  grid.addEventListener("focusout", () => tip.hide());
  $("#cal-legend").innerHTML = `<span>Next 5 trading days vs normal:</span><span class="neg">weaker</span><span class="grad" style="background:linear-gradient(90deg, ${css("--fail")}, #343B52, ${css("--accent")})"></span><span class="pos">stronger</span><span>(±1.5 points at full color)</span>`;
  const s = H.cells.slice().sort((a, b) => a.ex - b.ex), f = c => `${MON[c.m - 1]} ${c.d} (${ppts(c.ex, 1).replace(/<[^>]+>/g, "")})`;
  $("#cal-tell").innerHTML = `The weakest stretch was <strong>mid-to-late September (Sep 17–23)</strong>; the worst single dates were ${s.slice(0, 3).map(f).join(", ")}. The strongest were ${s.slice(-3).reverse().map(f).join(", ")}. Several streaks line up with the frozen windows (late September, mid-November, late March, early July), and like those windows, none passed the statistical tests. Treat the streaks as history, not a timetable.`;
}

/* ================================================================ E. comparison */
function compareTables() {
  const a = DATA.compare.is_, b = DATA.compare.oos, c = DATA.compare.consistency;
  const rows = [
    ["Average monthly return", "avg", pct(a.avg), pct(b.avg), ""],
    ["Median monthly return", "median", pct(a.median), pct(b.median), ""],
    ["Share of months that rose", "winrate", share(a.pct_pos), share(b.pct_pos), ""],
    ["Best calendar month (avg)", null, `${a.best_cal_month.m} ${pct(a.best_cal_month.avg)}`, `${b.best_cal_month.m} ${pct(b.best_cal_month.avg)} <span class="dim">(${b.best_cal_month.n} yrs)</span>`, ""],
    ["Worst calendar month (avg)", null, `${a.worst_cal_month.m} ${pct(a.worst_cal_month.avg)}`, `${b.worst_cal_month.m} ${pct(b.worst_cal_month.avg)} <span class="dim">(${b.worst_cal_month.n} yrs)</span>`, ""],
    ["Best single month", null, `${a.best_single.ym} ${pct(a.best_single.ret)}`, `${b.best_single.ym} ${pct(b.best_single.ret)}`, ""],
    ["Worst single month", null, `${a.worst_single.ym} ${pct(a.worst_single.ret)}`, `${b.worst_single.ym} ${pct(b.worst_single.ret)}`, ""],
    ["Average dip within a month", "mdd", pct(a.avg_mdd), pct(b.avg_mdd), ""],
    ["Deepest dip within a month", "mdd", pct(a.worst_mdd), pct(b.worst_mdd), ""],
    ["Month-to-month variability", "sd", pct(a.std, 2, false), pct(b.std, 2, false), ""],
    ["Seasonal consistency", "seasonality", `${c.is_split_half_same_sign} of 12 months<div class="dim" style="white-space:normal">same lean in 2003–12 and 2013–22</div>`, `${c.oos_same_sign_as_history_vs_own_avg} of 12 months<div class="dim" style="white-space:normal">same lean as 2003–22</div>`, ""],
  ];
  $("#tbl-compare").innerHTML = `<thead><tr><th class="l">Metric</th><th>2003–2022</th><th>2023–2026</th></tr></thead><tbody>${rows.map(r => `<tr><td class="l">${r[0]}${r[1] ? info(r[1]) : ""}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`).join("")}</tbody>`
    ;
  $("#tbl-compare").closest(".tw").insertAdjacentHTML("afterend", `<p class="caution" style="padding:8px 16px 0">"Seasonal consistency" asks two different questions, because 4 years can't be split in half. The left column checks whether the pattern was stable <i>within</i> the 20 historical years. The right column checks whether the newer years followed the <i>historical</i> pattern. 6 of 12 is what coin-flipping would give.</p>`);
  const pr = MON.map((mo, i) => {
    const is = M.is_[i], oo = M.oos[i];
    const hl = is.avg - M.is_avg_all, nl = oo.avg - M.oos_avg_all;
    return { m: mo, i, hl, nl, same: Math.sign(hl) === Math.sign(nl), v: M.oos_valid[mo], n: oo.n };
  });
  table($("#tbl-persist"), [
    { key: "m", label: "Month", l: true, sort: r => r.i, fmt: r => `<b>${r.m}</b>` },
    { key: "hl", label: "2003–22 vs typical", info: "excess", fmt: r => ppts(r.hl) },
    { key: "nl", label: "2023–26 vs typical", fmt: r => `${ppts(r.nl)} <span class="dim">(${r.n})</span>` },
    { key: "same", label: "Same lean?", sort: r => +r.same, fmt: r => r.same ? '<span class="pos">Yes</span>' : '<span class="neg">No</span>' },
    { key: "v", label: "Frozen verdict", info: "oos", l: true, sort: r => r.v, fmt: r => badge(OOS_BADGE, r.v) },
  ], pr, { sortKey: "m", dir: 1 });
  $("#tbl-persist").closest(".tw").insertAdjacentHTML("afterend", `<p class="caution" style="padding:8px 16px 12px">"Same lean?" compares each period with <i>its own</i> typical month. The frozen verdicts instead compare 2023–26 with the <i>2003–22</i> typical month (+0.71%), which the strong newer market beat easily. That is why July can be "Supportive" while its newer lean is slightly below the newer typical month. Numbers in brackets are the count of newer years.</p>`);
}

/* ================================================================ E. seasonal path */
function pathChart(view) {
  const el = $("#ch-path"), P = DATA.paths, W = 900, H = 300, m = { l: 44, r: 92, t: 10, b: 28 }, n = 252;
  const lines = [];
  if (view !== "recent") lines.push({ ys: P.is_avg, c: "var(--series-hist)", w: 2.5, lab: "2003–22 avg", name: "2003–2022 average (20 years)" });
  if (view === "recent") ["2023", "2024", "2025"].forEach(y => lines.push({ ys: P.oos_years[y], c: "var(--series-recent)", w: 1.2, op: .45, lab: y, name: y }));
  if (view !== "hist") { lines.push({ ys: P.oos_avg, c: "var(--series-recent)", w: 2.5, lab: "2023–25 avg", name: "2023–2025 average (3 years)" });
    lines.push({ ys: P.oos_years["2026"], c: "var(--highlight)", w: 2, dash: "5 4", lab: "2026 YTD", name: `2026 so far (to ${DATA.meta.oos_last})` }); }
  const all = lines.flatMap(l => l.ys); const lo = Math.min(...all, 100) - 1, hi = Math.max(...all) + 1;
  const X = i => m.l + i * (W - m.l - m.r) / (n - 1), Y = v => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Typical-year path of the S&P 500">`;
  ticks(lo, hi, 6).forEach(v => s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--border)"/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end" ${TXT}>${v}</text>`);
  s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(100)}" y2="${Y(100)}" stroke="var(--text-dim)" stroke-dasharray="3 3"/>`;
  let prev = ""; P.labels.forEach((l, i) => { const mo = l.slice(0, 2); if (mo !== prev) { s += `<text x="${X(i)}" y="${H - 8}" ${TXT}>${MON[+mo - 1]}</text>`; prev = mo; } });
  lines.forEach(l => { s += `<path d="${l.ys.slice(0, n).map((v, i) => (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1)).join("")}" fill="none" stroke="${l.c}" stroke-width="${l.w}" ${l.dash ? `stroke-dasharray="${l.dash}"` : ""} opacity="${l.op || 1}"/>`;
    const k = Math.min(l.ys.length, n) - 1; s += `<text x="${X(k) + 5}" y="${Y(l.ys[k]) + 4}" font-size="11" fill="${l.c}">${l.lab}</text>`; });
  s += `<line class="xh" y1="${m.t}" y2="${H - m.b}" stroke="var(--text-dim)" opacity="0"/><rect class="hit" x="${m.l}" y="0" width="${W - m.l - m.r}" height="${H}" fill="transparent"/></svg>`;
  el.innerHTML = s;
  const svg = $("svg", el), xh = $(".xh", svg), tip = chartTip(el);
  $(".hit", svg).addEventListener("pointermove", e => { const r = svg.getBoundingClientRect(); const i = Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) * W / r.width - m.l) / ((W - m.l - m.r) / (n - 1)))));
    xh.setAttribute("x1", X(i)); xh.setAttribute("x2", X(i)); xh.setAttribute("opacity", 1);
    tip.show(e, `<b>Trading day ${i + 1} · ~${mdLabel(P.labels[i])}</b><br>` + lines.map(l => l.ys[i] != null ? `${l.lab}: ${l.ys[i].toFixed(1)}` : "").filter(Boolean).join("<br>")); });
  $(".hit", svg).addEventListener("pointerleave", () => { tip.hide(); xh.setAttribute("opacity", 0); });
  $("#lg-path").innerHTML = lines.map(l => `<span><i class="${l.dash ? "dash" : "line"}" style="background:${l.c};border-color:${l.c};opacity:${l.op || 1}"></i>${l.name}</span>`).join("");
  const isEnd = P.is_avg[n - 1] - 100, ooEnd = P.oos_avg[n - 1] - 100, y26 = P.oos_years["2026"], ytd = y26[y26.length - 1] - 100;
  const tell = {
    hist: `Over 2003–2022 the average year finished about +${isEnd.toFixed(0)}%. It drifted sideways through the first quarter, rose through spring and summer, paused around September, then rose again into year-end. That shape is an average of very different years; few individual years looked like it.`,
    recent: `2023–2025 averaged about +${ooEnd.toFixed(0)}% a year, and 2026 was ${ytd >= 0 ? "+" : ""}${ytd.toFixed(0)}% through ${DATA.meta.oos_last}. The thin lines show how different the individual years were. 2025's spring plunge and recovery stands out.`,
    both: `The newer years rose faster almost all year long, which points to a stronger market rather than different seasonal timing. If seasonality were driving returns, the bumps and dips would line up between the two lines. Here they mostly don't.`
  }[view];
  $("#tell-path").innerHTML = `<div class="t">What does this chart tell me?</div>${tell}<div class="caution">Caution: the newer line is the average of 3 complete years and changes a lot with each year added.</div>`;
}

/* ================================================================ rule check */
function primaries() {
  const rows = DATA.primaries;
  table($("#tbl-primaries"), [
    { key: "rank", label: "#", fmt: r => `<span class="disclosure">▸</span>${r.rank}` },
    { key: "start", label: "Window", l: true, info: "window", sortable: false, fmt: r => `<b>${ruleLabel(r)}</b> <span class="dim">· ${r.days} td</span><br>${dirTxt(r.dir)}` },
    { key: "is_hit", label: "Then: right way", info: "is", fmt: r => share(r.is_hit) },
    { key: "is_mean", label: "Then: avg", fmt: r => pct(r.is_mean) },
    { key: "oos_n", label: "Now: years", info: "oos", fmt: r => r.oos_n },
    { key: "hits", label: "Now: right way", sort: r => r.hit_excess, fmt: r => { const k = r.occurrences.filter(o => o.status === "complete" && (r.dir === "bullish" ? o.ret > 0 : o.ret < 0)).length; return `${k} of ${r.oos_n}`; } },
    { key: "oos_mean", label: "Now: avg", fmt: r => pct(r.oos_mean) },
    { key: "oos_ex_drift", label: "vs random timing", info: "placebo", fmt: r => ppts(r.oos_ex_drift) },
    { key: "rho", label: "Edge kept", info: "rho", fmt: r => `${Math.round(r.rho * 100)}%` },
    { key: "verdict", label: "Verdict", l: true, sortable: false, fmt: r => `${badge(OOS_BADGE, r.verdict)}<div class="dim" style="font-size:11.5px">${r.effect}</div>` },
  ], rows, {
    sortKey: "rank", dir: 1, sortable: false,
    rowAttr: r => ` class="expandable" tabindex="0" aria-expanded="false" data-id="${r.id}"`,
    detail: (r, n) => `<tr class="detail" data-for="${r.id}" hidden><td colspan="${n}">${primaryDetail(r)}</td></tr>`,
    after: el => $$("tr.expandable", el).forEach(tr => { const tog = e => { if (e.target.closest("button.info")) return; const d = $(`tr[data-for="${tr.dataset.id}"]`, el); d.hidden = !d.hidden; tr.setAttribute("aria-expanded", String(!d.hidden)); $(".disclosure", tr).textContent = d.hidden ? "▸" : "▾"; };
      tr.addEventListener("click", tog); tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tog(e); } }); })
  });
}
function primaryDetail(r) {
  const occ = r.occurrences.map(o => o.status === "complete"
    ? `<tr><td class="l">${o.year}</td><td class="l">${o.entry}</td><td>${o.entry_px.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td><td class="l">${o.exit}</td><td>${o.exit_px.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td><td>${pct(o.ret)}</td><td>${pct(o.mdd)}</td><td>${(r.dir === "bullish" ? o.ret > 0 : o.ret < 0) ? '<span class="pos">✓</span>' : '<span class="neg">✗</span>'}</td></tr>`
    : `<tr><td class="l">${o.year}</td><td colspan="7" class="l"><span class="na">${esc(o.status)}: excluded</span></td></tr>`).join("");
  const sc = r.scorecard;
  return `<div class="grid2"><div><div class="tw"><table class="data"><thead><tr><th class="l">Year</th><th class="l">Bought (close)</th><th>Price</th><th class="l">Sold (close)</th><th>Price</th><th>Return</th><th>Worst dip${info("mdd")}</th><th>Right way?</th></tr></thead><tbody>${occ}</tbody></table></div>
    <p class="caution">Window ends are counted in trading days, so the exit date moves by a day or two between years (historically ${mdLabel(r.end_range[0])}–${mdLabel(r.end_range[1])}).</p></div>
    <div><table class="data"><tbody>
    <tr><td class="l">Historical years / p-value${info("pvalue")} / q-value${info("qvalue")}</td><td>${r.is_years} / ${r.is_p.toFixed(3)} / ${r.is_q.toFixed(2)}</td></tr>
    <tr><td class="l">Historical 95% range for the average${info("ci")}</td><td>${pct(r.is_ci[0])} to ${pct(r.is_ci[1])}</td></tr>
    <tr><td class="l">Newer 95% range for the average</td><td>${pct(r.oos_ci[0])} to ${pct(r.oos_ci[1])}</td></tr>
    <tr><td class="l">Newer excess vs 2003–22 baseline${info("baseline")}</td><td>${ppts(r.oos_ex_is)}</td></tr>
    <tr><td class="l">Newer excess vs 2023–26 drift${info("drift")}</td><td>${ppts(r.oos_ex_drift)}</td></tr>
    <tr><td class="l">Beat this share of random windows${info("placebo")}</td><td>${Math.round(r.placebo_pct * 100)}%</td></tr>
    <tr><td class="l">Scorecard: direction / win rate / size / dips / vs random</td><td style="white-space:normal">${[sc.direction_match, sc.win_rate, sc.return_consistency, sc.drawdown, sc.benchmark].join(" · ")}</td></tr>
    </tbody></table></div></div>`;
}
function isoosChart() {
  const el = $("#ch-isoos"), rows = DATA.primaries, W = 560, rowH = 42, m = { l: 150, r: 14, t: 6, b: 26 }, H = m.t + m.b + rows.length * rowH;
  const vals = rows.flatMap(r => [r.is_mean, r.oos_mean, r.oos_drift, 0]); const lo = Math.min(...vals) * 1.2, hi = Math.max(...vals) * 1.1;
  const X = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Average return then and now for each frozen window">`;
  ticks(lo, hi, 5).forEach(v => s += `<line x1="${X(v)}" x2="${X(v)}" y1="${m.t}" y2="${H - m.b}" stroke="var(--border)"/><text x="${X(v)}" y="${H - 8}" text-anchor="middle" ${TXT}>${(v * 100).toFixed(1)}%</text>`);
  s += `<line x1="${X(0)}" x2="${X(0)}" y1="${m.t}" y2="${H - m.b}" stroke="var(--text-dim)"/>`;
  rows.forEach((r, i) => { const y = m.t + i * rowH, bh = 12;
    s += `<text x="0" y="${y + 17}" font-size="12" fill="var(--text)">${ruleLabel(r)}</text><text x="0" y="${y + 31}" font-size="10.5" fill="${r.dir === "bullish" ? "var(--accent)" : "var(--fail)"}">${r.dir === "bullish" ? "▲ bullish" : "▼ bearish"} · ${r.days} td</text>`;
    [["is_mean", "var(--series-hist)", "2003–22 average", y + 7], ["oos_mean", "var(--series-recent)", "2023–26 average", y + 7 + bh + 2]].forEach(([k, c, lab, yy]) => { const v = r[k], x0 = Math.min(X(0), X(v)), w = Math.max(1.5, Math.abs(X(v) - X(0)));
      s += `<rect x="${x0}" y="${yy}" width="${w}" height="${bh}" rx="2" fill="${c}" data-t="<b>${ruleLabel(r)}</b><br>${lab}: ${pctPlain(v)}"/>`; });
    s += `<rect x="${X(r.oos_drift) - 1.5}" y="${y + 4}" width="3" height="${2 * bh + 8}" fill="var(--text-dim)" data-t="<b>${ruleLabel(r)}</b><br>Random ${r.days}-day window, 2023–26: ${pctPlain(r.oos_drift)}"/>`; });
  el.innerHTML = s + "</svg>"; chartTip(el);
  $("#lg-isoos").innerHTML = `<span><i style="background:var(--series-hist)"></i>2003–2022 average</span><span><i style="background:var(--series-recent)"></i>2023–2026 average</span><span><i style="background:var(--text-dim);width:3px"></i>random window, 2023–26</span>`;
}
function yearsChart() {
  const el = $("#ch-years"), rows = DATA.primaries, W = 560, rowH = 42, m = { l: 150, r: 14, t: 6, b: 26 }, H = m.t + m.b + rows.length * rowH;
  const YRS = [["2023", "var(--series-hist)", "circle"], ["2024", "var(--series-recent)", "square"], ["2025", "var(--accent)", "triangle"], ["2026", "var(--highlight)", "diamond"]];
  const vals = rows.flatMap(r => r.occurrences.filter(o => o.ret != null).map(o => o.ret)).concat([0]); const lo = Math.min(...vals) * 1.15, hi = Math.max(...vals) * 1.1;
  const X = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r);
  const mark = (sh, x, y, c, t) => { const a = `fill="${c}" stroke="#232939" stroke-width="1.5" ${t ? `data-t="${t}"` : ""}`;
    return sh === "circle" ? `<circle cx="${x}" cy="${y}" r="6" ${a}/>` : sh === "square" ? `<rect x="${x - 5.5}" y="${y - 5.5}" width="11" height="11" ${a}/>`
      : sh === "triangle" ? `<path d="M${x} ${y - 7}L${x + 6.5} ${y + 5}L${x - 6.5} ${y + 5}Z" ${a}/>` : `<path d="M${x} ${y - 7}L${x + 7} ${y}L${x} ${y + 7}L${x - 7} ${y}Z" ${a}/>`; };
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Each newer year's result for each frozen window">`;
  ticks(lo, hi, 5).forEach(v => s += `<line x1="${X(v)}" x2="${X(v)}" y1="${m.t}" y2="${H - m.b}" stroke="var(--border)"/><text x="${X(v)}" y="${H - 8}" text-anchor="middle" ${TXT}>${(v * 100).toFixed(0)}%</text>`);
  s += `<line x1="${X(0)}" x2="${X(0)}" y1="${m.t}" y2="${H - m.b}" stroke="var(--text-dim)"/>`;
  rows.forEach((r, i) => { const y = m.t + i * rowH + rowH / 2;
    s += `<text x="0" y="${y - 3}" font-size="12" fill="var(--text)">${ruleLabel(r)}</text><text x="0" y="${y + 11}" font-size="10.5" fill="${r.dir === "bullish" ? "var(--accent)" : "var(--fail)"}">${r.dir === "bullish" ? "▲ bullish" : "▼ bearish"} · ${r.days} td</text><line x1="${m.l}" x2="${W - m.r}" y1="${y}" y2="${y}" stroke="var(--border)" stroke-dasharray="2 3"/>`;
    YRS.forEach(([yr, c, sh], k) => { const o = r.occurrences.find(o => String(o.year) === yr && o.status === "complete"); if (!o) return;
      s += mark(sh, X(o.ret), y + (k - 1.5) * 2.5, c, `<b>${ruleLabel(r)} · ${yr}</b><br>${pctPlain(o.ret)} (${o.entry} → ${o.exit})`); }); });
  el.innerHTML = s + "</svg>"; chartTip(el);
  $("#lg-years").innerHTML = YRS.map(([y, c, sh]) => `<span><svg viewBox="-8 -8 16 16" width="14" height="14" style="vertical-align:-2px;margin-right:4px">${mark(sh, 0, 0, c, "")}</svg>${y}${y === "2026" ? " (completed windows only)" : ""}</span>`).join("");
}
function allRules() {
  const all = DATA.rules.map((r, i) => Object.assign({ i }, r));
  const t = table($("#tbl-rules"), [
    { key: "id", label: "Rule", l: true, sort: r => r.i, fmt: r => `<b>${esc(r.id)}</b>${r.primary ? ' <span class="badge ev-new">main</span>' : ""}` },
    { key: "window", label: "Window", l: true, sort: r => r.i, fmt: r => esc(r.window.replace("~", "").replace("Calendar month: ", "Whole month: ")) },
    { key: "dir", label: "Dir.", l: true, fmt: r => r.dir === "bullish" ? '<span class="pos" title="bullish">▲</span>' : '<span class="neg" title="bearish">▼</span>' },
    { key: "is_class", label: "2003–22 evidence", l: true, sort: r => ({ "Moderate Historical Evidence": 2, "Weak / Inconclusive": 1 })[r.is_class] || 0, fmt: r => badge(IS_BADGE, r.is_class) },
    { key: "is_mean", label: "Then avg", fmt: r => pct(r.is_mean) },
    { key: "oos_n", label: "Now N", fmt: r => r.oos_n },
    { key: "oos_mean", label: "Now avg", fmt: r => pct(r.oos_mean) },
    { key: "oos_ex_is", label: "vs 2003–22 base", info: "baseline", fmt: r => ppts(r.oos_ex_is) },
    { key: "oos_ex_drift", label: "vs 2023–26 drift", info: "drift", fmt: r => ppts(r.oos_ex_drift) },
    { key: "match", label: "Kept dir.?", sort: r => +r.match, fmt: r => r.match ? '<span class="pos">Yes</span>' : '<span class="neg">No</span>' },
    { key: "verdict", label: "Verdict", l: true, fmt: r => badge(OOS_BADGE, r.verdict) },
  ], all, { sortKey: "id", dir: 1 });
  const apply = () => { const q = $("#rule-search").value.trim().toLowerCase(), f = $("#rule-filter").value;
    const rs = all.filter(r => (!q || (r.id + " " + r.window).toLowerCase().includes(q)) && (!f || r.verdict === f)); t.setRows(rs); $("#rule-count").textContent = `${rs.length} of ${all.length} rules`; };
  $("#rule-search").addEventListener("input", apply); $("#rule-filter").addEventListener("change", apply); apply();
}

/* ================================================================ statistical review */
function review() {
  const S = DATA.sensitivity, s1 = S.S1_overlap_dependence, s2 = S.S2_same_year_placebo, s3 = S.S3_cross_rule_tests, s4 = S.S4_entry_exit, s5 = S.S5_partial_2026;
  const ok = '<span class="badge ev-supp">Confirms original</span>', qual = '<span class="badge ev-inc">Qualifies original</span>';
  const rows = [
    ["Overlapping windows (2003–2022)", "Windows like Jul 1 + 15 days and Jul 1 + 20 days share most of their days, so the 120 tests are not independent.",
      `Best q-value ${s1.original_min_bh_q.toFixed(2)}; permutation family-wise p ${s1.original_min_perm_fwer_p.toFixed(2)}. Nothing significant.`,
      `The 120 windows behave like about ${Math.round(s1.effective_independent_tests_li_ji)} independent tests. Even crediting that, the best window's adjusted p is ${s1.best_p_bonferroni_at_m_eff.toFixed(2)}, still not significant. Using the Wilcoxon test instead of the t-test gives a best q of ${s1.min_bh_q_using_wilcoxon_instead_of_t.toFixed(2)}.`, ok],
    ["Placebo environment (2023–2026)", "Comparing a 2024 trade with random windows from 2023 or 2025 mixes in different market conditions.",
      `Bullish windows vs random timing: p = ${s2.original_reported_p.toFixed(2)}.`,
      `Keeping each placebo inside the same calendar year gives p = ${s2.variants.same_calendar_year.p_one_sided.toFixed(2)}; fully independent random dates give p = ${s2.variants.anywhere_in_2023_2026.p_one_sided.toFixed(2)}. Same conclusion: no better than random timing.`, ok],
    ["Spearman and binomial tests across 132 rules", "These tests treated all 132 rules as independent, but many overlap, which makes p-values too small.",
      `"Historical winners stayed ahead": Spearman ${s3.observed_spearman.toFixed(2)}, p = ${s3.original_reported_p_spearman.toFixed(3)} (nominal). Share keeping direction ${Math.round(s3.observed_share_same_direction_vs_is_base * 100)}%, p = ${s3.original_reported_p_binomial.toFixed(2)}.`,
      `Shifting every rule's dates together (which keeps the overlaps) gives Spearman p = ${s3.calendar_shift_p_spearman.toFixed(2)} and share p = ${s3.calendar_shift_p_share.toFixed(2)}. The faint persistence is within the range luck produces.`, qual],
    ["Entry and exit timing", "A window might hold one day too many or too few, or its label might not match the dates actually used.",
      "Entries at the close before the start date; exits at the close of the Nth trading day.",
      `All ${s4.primary_occurrences_checked} newer-period trades for the 8 main rules match that definition. Labels like "Jul 1 → Jul 22" show the typical exit; the real exit varies by 1–3 days. January 2023 rules started from the Jan 3 open (no earlier price in the new file). Using the Dec 30, 2022 close instead would change January 2023 from ${pctPlain(s4.jan_2023_entry.jan_2023_month_return_as_reported)} to ${pctPlain(s4.jan_2023_entry.jan_2023_month_return_from_prior_close)}. That affects 6 January rules, none of them a main rule.`, ok],
    ["Unfinished 2026 periods", "Counting a half-finished October or a window still open would mix partial results with complete ones.",
      "Occurrences ending after Oct 2, 2026 were labelled incomplete and excluded.",
      `${s5.incomplete_occurrences} incomplete occurrences found and ${s5.any_incomplete_has_return ? "SOME" : "none"} of them carry a return. ${s5.rules_with_N_3.length} rules (October to December windows, plus late-September ones) therefore have 3 newer years instead of 4. That is correct, but it leaves them with slightly less evidence.`, ok],
  ];
  $("#tbl-review").innerHTML = `<thead><tr><th class="l">Check</th><th class="l">What could go wrong</th><th class="l">Original result</th><th class="l">Sensitivity result (new)</th><th class="l">Effect</th></tr></thead><tbody>`
    + rows.map(r => `<tr><td class="l wrap"><b>${r[0]}</b></td><td class="l wrap">${r[1]}</td><td class="l wrap">${r[2]}</td><td class="l wrap">${r[3]}</td><td class="l">${r[4]}</td></tr>`).join("") + "</tbody>";
}

/* ================================================================ glossary */
function glossary() {
  $("#gl-terms").innerHTML = GLOSSARY.terms.map(t => `<article class="gl" id="g-${t.id}" data-s="${esc((t.term + " " + t.meaning).toLowerCase())}"><h3>${esc(t.term)}</h3>
    <div><div class="k">What does it mean?</div><p>${esc(t.meaning)}</p></div><div><div class="k">Why does it matter?</div><p>${esc(t.why)}</p></div><div><div class="k">Simple example</div><p>${esc(t.example)}</p></div></article>`).join("");
  $("#gl-formulas").innerHTML = GLOSSARY.formulas.map(f => `<article class="gl" id="f-${f.id}" data-s="${esc((f.name + " " + f.formula).toLowerCase())}"><h3>${esc(f.name)}</h3><div class="formula">${esc(f.formula)}</div>
    ${f.symbols.length ? `<dl class="syms">${f.symbols.map(s => `<dt>${esc(s[0])}</dt><dd>${esc(s[1])}</dd>`).join("")}</dl>` : ""}
    <div><div class="k">Worked example</div><p>${esc(f.worked)}</p></div><div><div class="k">Higher or lower means</div><p>${esc(f.reading)}</p></div><div><div class="k">Limitations</div><p>${esc(f.limits)}</p></div></article>`).join("");
  const cards = $$("#glossary .gl");
  const apply = () => { const q = $("#gl-search").value.trim().toLowerCase(); let n = 0; cards.forEach(c => { const hit = !q || c.dataset.s.includes(q); c.hidden = !hit; n += hit; }); $("#gl-count").textContent = `${n} of ${cards.length} entries`; };
  $("#gl-search").addEventListener("input", apply); apply();
}

/* ================================================================ toggles + nav */
function toggles() {
  $$(".seg[data-chart]").forEach(g => g.addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
    $$("button", g).forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    ({ months: monthsChart, path: pathChart })[g.dataset.chart](b.dataset.v); }));
  const links = $$("nav.tabs a"), secs = links.map(a => $(a.getAttribute("href")));
  if ("IntersectionObserver" in window) { const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) links.forEach(a => a.classList.toggle("active", a.getAttribute("href") === "#" + en.target.id)); }), { rootMargin: "-30% 0px -60% 0px" });
    secs.forEach(s => s && io.observe(s)); }
}

monthsChart("hist"); monthTables(); windowsHist();
heatTable($("#heat-hist-tbl"), DATA.heat.is_, DATA.heat.is_month_avg, "Each month: last close ÷ previous month's last close − 1. January 2003 starts from the Jan 2 open.");
heatTable($("#heat-new-tbl"), DATA.heat.oos, DATA.heat.oos_month_avg, "Same calculation. January 2023 starts from the Jan 3 open, as the frozen study did. Averages use completed months only.", DATA.heat.oos_month_n);
heatLegend($("#heat-legend-1")); heatLegend($("#heat-legend-2")); recentDataNote(); calendarHeat();
compareTables(); pathChart("both"); primaries(); isoosChart(); yearsChart(); allRules(); review(); glossary(); toggles();
})();
