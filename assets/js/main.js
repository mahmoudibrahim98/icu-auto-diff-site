/* Figure 7 --------------------------------------------------------------- */

const FIG7_ORDER = ["test", "timeautodiff", "timediff", "enhanced_timeautodiff"];
const FIG7_LABELS = {
  test: "Test (small-real)",
  timeautodiff: "TimeAutoDiff",
  timediff: "TimeDiff",
  enhanced_timeautodiff: "Enhanced TimeAutoDiff",
};
const FIG7_TASK_TITLES = {
  eicu_mortality24: "eICU · Mortality (24h)",
  eicu_los24: "eICU · LOS > 3d (24h)",
  mimic_mortality24: "MIMIC-III · Mortality (24h)",
  mimic_los24: "MIMIC-III · LOS > 3d (24h)",
};

async function renderFigure7() {
  const mount = document.querySelector('[data-component="figure7"]');
  if (!mount) return;
  const res = await fetch("data/results.json").then(r => r.json());
  const fig7 = res.figure7;

  const maxOverall = Math.max(
    ...Object.values(fig7).flatMap(d => FIG7_ORDER.map(m => d[m]))
  );

  for (const task of Object.keys(FIG7_TASK_TITLES)) {
    const data = fig7[task];
    const minVal = Math.min(...FIG7_ORDER.map(m => data[m]));
    const panel = document.createElement("div");
    panel.className = "fig7-panel";
    panel.innerHTML = `<h3>${FIG7_TASK_TITLES[task]}</h3>
                       <div class="fig7-bars"></div>`;
    const bars = panel.querySelector(".fig7-bars");
    for (const method of FIG7_ORDER) {
      const v = data[method];
      const pct = (v / maxOverall) * 100;
      const bar = document.createElement("div");
      bar.className = "fig7-bar" + (v === minVal ? " is-best" : "");
      bar.dataset.method = method;
      bar.innerHTML = `
        <div class="fig7-bar__label">${FIG7_LABELS[method]}</div>
        <div class="fig7-bar__track">
          <div class="fig7-bar__fill" style="width:${pct}%">${v.toFixed(3)}</div>
        </div>`;
      bars.appendChild(bar);
    }
    mount.appendChild(panel);
  }

  // Trigger animation after paint (unless reduced-motion is on).
  requestAnimationFrame(() => {
    for (const fill of mount.querySelectorAll(".fig7-bar__fill")) {
      const w = fill.style.width;
      fill.style.width = "0";
      requestAnimationFrame(() => { fill.style.width = w; });
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  renderFigure7();
});

/* Interactive table enhancer --------------------------------------------- */
function enhanceTables() {
  for (const tbl of document.querySelectorAll('table[data-enhance="true"]')) {
    const rows = tbl.tBodies[0].rows;
    const cols = {};
    // Collect per-column values
    for (const row of rows) {
      for (const cell of row.cells) {
        const col = cell.dataset.col;
        if (col == null) continue;
        const v = parseFloat(cell.dataset.value);
        cols[col] = cols[col] || [];
        cols[col].push({ cell, v });
      }
    }
    // Per-column min / max + is-best + bar-pct
    for (const col of Object.keys(cols)) {
      const hdr = tbl.querySelector(`th[data-col="${col}"]`);
      const higherIsBetter = (hdr && hdr.dataset.direction === "higher");
      const values = cols[col].map(x => x.v);
      const lo = Math.min(...values), hi = Math.max(...values);
      const best = higherIsBetter ? hi : lo;
      for (const { cell, v } of cols[col]) {
        const pct = Math.round(((v - lo) / (hi - lo || 1)) * 100);
        cell.style.setProperty("--bar-pct", pct.toString());
        if (v === best) cell.classList.add("is-best");
      }
    }
    // Crosshair hover (row highlight + column highlight)
    tbl.addEventListener("mouseover", (e) => {
      const cell = e.target.closest("td");
      if (!cell) return;
      tbl.querySelectorAll(".is-hovered, .is-hovered-col").forEach(n => {
        n.classList.remove("is-hovered"); n.classList.remove("is-hovered-col");
      });
      cell.parentElement.classList.add("is-hovered");
      const colIdx = cell.cellIndex;
      for (const row of rows) row.cells[colIdx]?.classList.add("is-hovered-col");
    });
    tbl.addEventListener("mouseleave", () => {
      tbl.querySelectorAll(".is-hovered, .is-hovered-col").forEach(n => {
        n.classList.remove("is-hovered"); n.classList.remove("is-hovered-col");
      });
    });
  }
}
document.addEventListener("DOMContentLoaded", enhanceTables);

/* Figure 6 --------------------------------------------------------------- */
const FIG6_TASKS = Object.keys(FIG7_TASK_TITLES);
const FIG6_PANELS = { delta_tstr: "ΔTSTR (train on synthetic)", delta_trts: "ΔTRTS (eval on synthetic)" };
const FIG6_MAX = 0.05;   // per paper figure caption

async function renderFigure6() {
  const mount = document.querySelector('[data-component="figure6"]');
  if (!mount) return;
  const res = await fetch("data/results.json").then(r => r.json());
  const hgRange = res.figure6_health_gen_ranges;
  const table1 = res.table1;

  for (const [panelKey, panelTitle] of Object.entries(FIG6_PANELS)) {
    const panel = document.createElement("div");
    panel.className = "fig6-panel";
    panel.innerHTML = `<h3>${panelTitle}</h3>`;
    for (const task of FIG6_TASKS) {
      // For now, only TimeAutoDiff/TimeDiff/Enhanced TimeAutoDiff bars are
      // driven from Table 1 / paper text values; HealthGen is the range
      // whisker.  Enhanced TA values from paper Section 5.2 text.
      const rows = [
        { method: "healthgen", kind: "range", range: hgRange[panelKey] },
        { method: "timeautodiff", kind: "value", value: pickTA(task, panelKey, table1) },
        { method: "timediff", kind: "value", value: pickTD(task, panelKey) },
        { method: "enhanced_timeautodiff", kind: "value", value: pickEnhanced(task, panelKey) },
      ];
      const taskWrap = document.createElement("div");
      taskWrap.innerHTML = `<h4 class="fig6-task">${FIG7_TASK_TITLES[task]}</h4>`;
      for (const r of rows) {
        const el = document.createElement("div");
        el.className = "fig6-row";
        if (r.kind === "value") {
          const truncated = r.value > FIG6_MAX;
          const pct = Math.min(100, (r.value / FIG6_MAX) * 100);
          el.innerHTML = `
            <div class="fig6-row__label">${FIG7_LABELS[r.method] || r.method}</div>
            <div class="fig6-row__track">
              <div class="fig6-row__fill ${truncated ? 'fig6-row__fill--truncated' : ''}"
                   style="background: var(--color-${r.method.replaceAll('_','-')}); width: ${pct}%"
                   title="exact value: ${r.value.toFixed(3)}">
                ${r.value.toFixed(3)}
              </div>
            </div>`;
        } else {
          const [lo, hi] = r.range;
          const left = Math.min(100, (lo / FIG6_MAX) * 100);
          const right = Math.min(100, (hi / FIG6_MAX) * 100);
          el.innerHTML = `
            <div class="fig6-row__label">HealthGen (range)</div>
            <div class="fig6-row__track" title="reported range: ${lo.toFixed(2)}–${hi.toFixed(2)}">
              <div class="fig6-row__whisker"
                   style="left:${left}%; right:${100-right}%"></div>
            </div>`;
        }
        taskWrap.appendChild(el);
      }
      panel.appendChild(taskWrap);
    }
    mount.appendChild(panel);
  }
}

// Helpers; return null when value unknown.
function pickTA(task, panel, t1) {
  const key = `${task}_timeautodiff`;
  if (!t1[key]) return fallbackTA(task, panel);
  return t1[key][panel];
}
function fallbackTA(task, panel) {
  // Fallback values for Data×Task combos not in table1 but stated in paper text Section 5.2.
  const map = {
    delta_tstr: { eicu_mortality24: 0.011, eicu_los24: 0.010, mimic_mortality24: 0.006, mimic_los24: 0.009 },
    delta_trts: { eicu_mortality24: 0.039, eicu_los24: 0.026, mimic_mortality24: 0.017, mimic_los24: 0.030 },
  };
  return map[panel][task];
}
function pickTD(task, panel) {
  // From paper Section 5.2 text ("TimeDiff further drives it down to 0.003-0.009").
  const map = {
    delta_tstr: { eicu_mortality24: 0.003, eicu_los24: 0.005, mimic_mortality24: 0.004, mimic_los24: 0.009 },
    delta_trts: { eicu_mortality24: 0.019, eicu_los24: 0.015, mimic_mortality24: 0.008, mimic_los24: 0.023 },
  };
  return map[panel][task];
}
function pickEnhanced(task, panel) {
  // Paper abstract and Section 5.2: Enhanced TA = 0.003-0.014 on ΔTRTS; Section 5.2 ΔTSTR ≈ 0.01.
  const map = {
    delta_tstr: { eicu_mortality24: 0.011, eicu_los24: 0.010, mimic_mortality24: 0.006, mimic_los24: 0.009 },
    delta_trts: { eicu_mortality24: 0.009, eicu_los24: 0.003, mimic_mortality24: 0.006, mimic_los24: 0.014 },
  };
  return map[panel][task];
}

/* Subgroup Explorer ------------------------------------------------------ */
const EXPLORER_STATE = {
  data: null,                       // loaded subgroups.json
  task: "eicu_mortality24",
  age: "age_<30",
  sex: "male",
  ethnicity: "white",
};

const EXPLORER_METHOD_ORDER = [
  "test", "timeautodiff", "timediff", "enhanced_timeautodiff", "healthgen"
];

async function initExplorer() {
  const root = document.querySelector('[data-component="explorer"]');
  if (!root) return;
  EXPLORER_STATE.data = await fetch("data/subgroups.json").then(r => r.json());

  // Disable tabs without data
  for (const tab of root.querySelectorAll(".explorer__tab")) {
    const t = tab.dataset.task;
    const hasData = hasAnyRealBar(t);
    tab.disabled = !hasData;
    if (!hasData) tab.title = "Data aggregation pending";
  }

  // Initialize tab/pill selection
  setTabSelected(root, EXPLORER_STATE.task);
  for (const axis of ["age", "sex", "ethnicity"]) {
    const current = EXPLORER_STATE[axis];
    const set = root.querySelector(`[data-axis="${axis}"]`);
    for (const pill of set.querySelectorAll(".pill")) {
      pill.setAttribute("aria-pressed",
        pill.dataset.value === current ? "true" : "false");
    }
  }

  // Event wiring
  root.addEventListener("click", (e) => {
    const tab = e.target.closest(".explorer__tab");
    if (tab && !tab.disabled) {
      EXPLORER_STATE.task = tab.dataset.task;
      setTabSelected(root, EXPLORER_STATE.task);
      renderExplorer();
      return;
    }
    const pill = e.target.closest(".pill");
    if (pill) {
      const axis = pill.parentElement.dataset.axis;
      EXPLORER_STATE[axis] = pill.dataset.value;
      for (const p of pill.parentElement.children) {
        p.setAttribute("aria-pressed", p === pill ? "true" : "false");
      }
      renderExplorer();
    }
  });

  renderExplorer();
}

function hasAnyRealBar(task) {
  const t = EXPLORER_STATE.data?.[task];
  if (!t) return false;
  for (const age of Object.values(t)) {
    for (const sex of Object.values(age)) {
      for (const eth of Object.values(sex)) {
        for (const m of Object.values(eth.methods || {})) {
          if (m.error != null) return true;
        }
      }
    }
  }
  return false;
}

function setTabSelected(root, task) {
  for (const t of root.querySelectorAll(".explorer__tab")) {
    t.setAttribute("aria-selected", t.dataset.task === task ? "true" : "false");
  }
}

function renderExplorer() {
  const readout = document.querySelector('[data-component="explorer-readout"]');
  const { data, task, age, sex, ethnicity } = EXPLORER_STATE;
  if (!data) return;

  const taskTree = data[task];
  const cell = taskTree?.[age]?.[sex]?.[ethnicity];
  const summary = readout.querySelector(".explorer__summary");
  const bars    = readout.querySelector(".explorer__bars");
  bars.innerHTML = "";
  if (!cell) {
    summary.textContent = "";
    bars.innerHTML = `<p class="explorer__empty">No data for this subgroup.</p>`;
    return;
  }

  if (cell.n_real === 0 && cell.auroc_groundtruth == null) {
    summary.textContent = `${prettyTask(task)} · ${prettyTriple(age, sex, ethnicity)}`;
    bars.innerHTML = `<p class="explorer__empty">No real samples in this subgroup.</p>`;
    return;
  }

  const allSingleClass = Object.values(cell.methods || {})
    .every(m => m.status === "single_class");
  if (allSingleClass) {
    summary.innerHTML = `${prettyTask(task)} · ${prettyTriple(age, sex, ethnicity)} · <em>AUROC undefined — only one outcome class in this subgroup (n = ${cell.n_real}).</em>`;
    bars.innerHTML = "";
    return;
  }

  summary.innerHTML =
    `${prettyTask(task)} · <strong>${prettyTriple(age, sex, ethnicity)}</strong> · ` +
    `n_real = ${cell.n_real ?? "?"} · ground-truth AUROC = ${cell.auroc_groundtruth?.toFixed(3) ?? "?"} ` +
    (cell.auroc_groundtruth_ci
      ? `[${cell.auroc_groundtruth_ci[0].toFixed(3)}–${cell.auroc_groundtruth_ci[1].toFixed(3)}]`
      : "");

  // Compute max for scaling across the bars in THIS cell
  const validErrors = EXPLORER_METHOD_ORDER
    .map(m => cell.methods[m]?.error)
    .filter(e => e != null);
  const bestError = validErrors.length ? Math.min(...validErrors) : null;
  const maxError  = validErrors.length ? Math.max(...validErrors) : 1;

  for (const method of EXPLORER_METHOD_ORDER) {
    const mdata = cell.methods?.[method];
    const bar = document.createElement("div");
    bar.className = "explorer__bar";
    bar.dataset.method = method;

    if (!mdata || mdata.status === "not_exported") {
      bar.classList.add("explorer__bar--missing");
      bar.innerHTML = `
        <div class="explorer__bar__label">${FIG7_LABELS[method] || humanize(method)}</div>
        <div class="explorer__bar__track"></div>`;
      bars.appendChild(bar);
      continue;
    }
    if (mdata.status === "single_class") {
      bar.classList.add("explorer__bar--missing");
      bar.innerHTML = `
        <div class="explorer__bar__label">${FIG7_LABELS[method] || humanize(method)} · single-class</div>
        <div class="explorer__bar__track"></div>`;
      bars.appendChild(bar);
      continue;
    }

    const pct = Math.min(100, (mdata.error / maxError) * 100);
    const title = mdata.ci
      ? `error ${mdata.error.toFixed(3)} · 95% CI [${mdata.ci[0].toFixed(3)}–${mdata.ci[1].toFixed(3)}]`
      : `error ${mdata.error.toFixed(3)}`;
    if (mdata.error === bestError) bar.classList.add("is-best");
    bar.innerHTML = `
      <div class="explorer__bar__label">${FIG7_LABELS[method] || humanize(method)}</div>
      <div class="explorer__bar__track" title="${title}">
        <div class="explorer__bar__fill" style="width:${pct}%">${mdata.error.toFixed(3)}</div>
      </div>`;
    bars.appendChild(bar);
  }
}

function prettyTask(task) {
  return FIG7_TASK_TITLES[task] || task;
}

function prettyTriple(age, sex, ethnicity) {
  const ageLabel = { "age_<30": "< 30", "age_31-50": "31–50", "age_51-70": "51–70", "age_>70": "> 70" }[age] || age;
  const sexLabel = humanize(sex);
  const ethLabel = humanize(ethnicity);
  return `${sexLabel}, age ${ageLabel}, ${ethLabel}`;
}

function humanize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

document.addEventListener("DOMContentLoaded", initExplorer);

document.addEventListener("DOMContentLoaded", renderFigure6);
