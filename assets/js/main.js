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
