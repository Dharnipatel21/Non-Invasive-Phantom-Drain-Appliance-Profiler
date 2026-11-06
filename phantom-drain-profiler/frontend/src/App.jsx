import React, { useEffect, useState } from "react";

const COLORS = { active: "#38bdf8", standby: "#f59e0b", off: "#64748b" };
const get = (url) => fetch(url).then((r) => r.json());

function Card({ a, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition ${
        selected ? "border-sky-400 bg-slate-800" : "border-slate-800 bg-slate-900 hover:bg-slate-800"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium">{a.name}</span>
        <span
          className="rounded-full px-2 py-0.5 text-xs font-semibold uppercase text-slate-950"
          style={{ background: COLORS[a.status] }}
        >
          {a.status}
        </span>
      </div>
      <div className="mt-3 text-3xl font-semibold tabular-nums">
        {a.power_w.toFixed(1)} <span className="text-base text-slate-400">W</span>
      </div>
      {a.status === "standby" && <div className="mt-1 text-xs text-amber-400">Phantom drain detected</div>}
    </button>
  );
}

function Chart({ data }) {
  const W = 700, H = 220, P = 30;
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.power_w), 20);
  const x = (i) => P + (i / (data.length - 1)) * (W - 2 * P);
  const y = (v) => H - P - (v / max) * (H - 2 * P);
  const pts = data.map((d, i) => `${x(i)},${y(d.power_w)}`).join(" ");
  const standbyY = y(15);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={P} x2={W - P} y1={y(max * t)} y2={y(max * t)} stroke="#1e293b" />
          <text x={4} y={y(max * t) + 4} fontSize="10" fill="#94a3b8">
            {Math.round(max * t)}
          </text>
        </g>
      ))}
      <line x1={P} x2={W - P} y1={standbyY} y2={standbyY} stroke="#f59e0b" strokeDasharray="4 4" />
      <text x={W - P} y={standbyY - 4} fontSize="10" fill="#f59e0b" textAnchor="end">
        active threshold 15 W
      </text>
      <polyline points={pts} fill="none" stroke="#38bdf8" strokeWidth="2" />
    </svg>
  );
}

function Bars({ rows }) {
  const max = Math.max(...rows.map((r) => r.annual_kwh), 1);
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.name}>
          <div className="flex justify-between text-sm">
            <span>{r.name}</span>
            <span className="tabular-nums text-slate-400">
              {r.annual_kwh} kWh/yr · {r.avg_standby_w} W avg standby
            </span>
          </div>
          <div className="mt-1 h-2 rounded bg-slate-800">
            <div className="h-2 rounded bg-amber-500" style={{ width: `${(r.annual_kwh / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [apps, setApps] = useState([]);
  const [sum, setSum] = useState(null);
  const [sel, setSel] = useState(null);
  const [hist, setHist] = useState([]);

  useEffect(() => {
    const tick = async () => {
      const [a, s] = await Promise.all([get("/api/appliances"), get("/api/summary")]);
      setApps(a);
      setSum(s);
      setSel((cur) => cur || a[0]?.name);
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!sel) return;
    const load = () => get(`/api/history/${encodeURIComponent(sel)}`).then(setHist);
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [sel]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Phantom Drain Appliance Profiler</h1>
        <p className="text-sm text-slate-400">Non-invasive standby power monitoring · live</p>
      </header>

      {sum && (
        <section className="grid gap-4 sm:grid-cols-3">
          {[
            ["Phantom load now", `${sum.phantom_now_w} W`],
            ["Projected waste", `${sum.annual_kwh} kWh/yr`],
            ["Projected cost", `₹${sum.annual_cost_inr}/yr`],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
              <div className="text-sm text-slate-400">{k}</div>
              <div className="mt-1 text-3xl font-semibold text-amber-400">{v}</div>
            </div>
          ))}
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {apps.map((a) => (
          <Card key={a.name} a={a} selected={a.name === sel} onClick={() => setSel(a.name)} />
        ))}
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-2 font-medium">Power trace · {sel}</h2>
        <Chart data={hist} />
      </section>

      {sum && (
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 font-medium">Projected yearly standby energy by appliance</h2>
          <Bars rows={sum.per_appliance} />
          <p className="mt-3 text-xs text-slate-500">Tariff ₹{sum.tariff_inr_per_kwh}/kWh</p>
        </section>
      )}
    </div>
  );
}
