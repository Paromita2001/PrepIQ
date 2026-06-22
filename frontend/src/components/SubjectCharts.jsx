import { useState } from "react";
import MasteryHeatmap from "./MasteryHeatmap";

const SUBJECTS_6 = ["English", "Mathematics", "Science", "Social Science", "Hindi", "Sanskrit"];

const SHORT = {
  "English":       "English",
  "Mathematics":   "Maths",
  "Science":       "Science",
  "Social Science":"SST",
  "Hindi":         "Hindi",
  "Sanskrit":      "Sanskrit",
};

function barColor(m) {
  if (m === undefined || m === null) return "#374151";
  if (m >= 0.8) return "#22c55e";
  if (m >= 0.6) return "#16a34a";
  if (m >= 0.4) return "#ca8a04";
  if (m >= 0.2) return "#ea580c";
  return "#dc2626";
}

function barLabel(m) {
  if (m === undefined || m === null) return "No data";
  if (m >= 0.8) return "Strong";
  if (m >= 0.6) return "Good";
  if (m >= 0.4) return "Average";
  if (m >= 0.2) return "Weak";
  return "Very Weak";
}

function BarChart({ subjectAvg, selected, onSelect }) {
  const W = 560, H = 210;
  const pL = 38, pR = 12, pT = 20, pB = 56;
  const cW = W - pL - pR;
  const cH = H - pT - pB;
  const n = SUBJECTS_6.length;
  const slot = cW / n;
  const bW = Math.floor(slot * 0.52);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 230 }}>
      {[0, 25, 50, 75, 100].map(pct => {
        const y = pT + cH - (pct / 100) * cH;
        return (
          <g key={pct}>
            <line x1={pL} x2={W - pR} y1={y} y2={y} stroke="#1f2937" strokeWidth={1} />
            <text x={pL - 5} y={y + 4} textAnchor="end" fontSize={9} fill="#6b7280">{pct}%</text>
          </g>
        );
      })}

      {SUBJECTS_6.map((sub, i) => {
        const m = subjectAvg[sub];
        const pct = (m !== undefined && m !== null) ? m * 100 : 0;
        const bH = Math.max(4, (pct / 100) * cH);
        const x = pL + i * slot + (slot - bW) / 2;
        const y = pT + cH - bH;
        const color = barColor(m);
        const active = selected === sub;

        return (
          <g key={sub} style={{ cursor: "pointer" }} onClick={() => onSelect(active ? null : sub)}>
            <rect
              x={x} y={y} width={bW} height={bH}
              fill={color} rx={4}
              opacity={active ? 1 : 0.72}
              stroke={active ? "#60a5fa" : "none"}
              strokeWidth={2}
            />
            {m !== undefined && m !== null && (
              <text x={x + bW / 2} y={y - 5} textAnchor="middle" fontSize={10} fill="#e5e7eb" fontWeight="600">
                {pct.toFixed(0)}%
              </text>
            )}
            <text x={x + bW / 2} y={pT + cH + 15} textAnchor="middle" fontSize={10}
              fill={active ? "#60a5fa" : "#9ca3af"} fontWeight={active ? "600" : "400"}>
              {SHORT[sub]}
            </text>
            <text x={x + bW / 2} y={pT + cH + 28} textAnchor="middle" fontSize={9} fill={color}>
              {barLabel(m)}
            </text>
          </g>
        );
      })}

      <line x1={pL} x2={W - pR} y1={pT + cH} y2={pT + cH} stroke="#374151" strokeWidth={1} />
    </svg>
  );
}

function TrendChart({ sessions }) {
  const done = sessions
    .filter(s => s.total_score !== null && s.total_marks)
    .slice(-10)
    .map(s => ({
      pct: (s.total_score / s.total_marks) * 100,
      date: new Date(s.started_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
      subject: s.subject_name || "",
    }));

  if (done.length < 2) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500 text-sm text-center px-4">
        Complete at least 2 graded tests<br />to see your score trend.
      </div>
    );
  }

  const W = 560, H = 210;
  const pL = 38, pR = 12, pT = 20, pB = 56;
  const cW = W - pL - pR;
  const cH = H - pT - pB;

  const pts = done.map((s, i) => ({
    x: pL + (i / (done.length - 1)) * cW,
    y: pT + cH - (s.pct / 100) * cH,
    ...s,
  }));

  const line = pts.map(p => `${p.x},${p.y}`).join(" ");
  const area = [
    `M ${pts[0].x} ${pT + cH}`,
    ...pts.map(p => `L ${p.x} ${p.y}`),
    `L ${pts[pts.length - 1].x} ${pT + cH} Z`,
  ].join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 230 }}>
      <defs>
        <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#3b82f6" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {[0, 25, 50, 75, 100].map(pct => {
        const y = pT + cH - (pct / 100) * cH;
        return (
          <g key={pct}>
            <line x1={pL} x2={W - pR} y1={y} y2={y} stroke="#1f2937" strokeWidth={1} />
            <text x={pL - 5} y={y + 4} textAnchor="end" fontSize={9} fill="#6b7280">{pct}%</text>
          </g>
        );
      })}

      <path d={area} fill="url(#trendFill)" />
      <polyline points={line} fill="none" stroke="#3b82f6" strokeWidth={2.5} strokeLinejoin="round" />

      {pts.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={4.5} fill="#3b82f6" stroke="#111827" strokeWidth={2} />
          <text x={p.x} y={p.y - 9} textAnchor="middle" fontSize={9} fill="#e5e7eb" fontWeight="600">
            {p.pct.toFixed(0)}%
          </text>
          <text
            x={p.x} y={pT + cH + 14}
            textAnchor="end" fontSize={9} fill="#6b7280"
            transform={`rotate(-40 ${p.x} ${pT + cH + 14})`}
          >
            {p.date}
          </text>
        </g>
      ))}

      <line x1={pL} x2={W - pR} y1={pT + cH} y2={pT + cH} stroke="#374151" strokeWidth={1} />
    </svg>
  );
}

export default function SubjectCharts({ subjectAvg, allMastery, sessions }) {
  const [selected, setSelected] = useState(null);

  return (
    <div className="space-y-5">
      {/* Two charts side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="font-semibold text-gray-200 mb-1 text-sm">Subject Mastery</h3>
          <p className="text-xs text-gray-500 mb-3">Click a bar to see topic breakdown</p>
          <BarChart subjectAvg={subjectAvg} selected={selected} onSelect={setSelected} />
        </div>

        <div className="card">
          <h3 className="font-semibold text-gray-200 mb-1 text-sm">Score Trend</h3>
          <p className="text-xs text-gray-500 mb-3">Last 10 completed tests</p>
          <TrendChart sessions={sessions} />
        </div>
      </div>

      {/* Topic drill-down */}
      {selected && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-200">{selected} — Topic Breakdown</h3>
            <button onClick={() => setSelected(null)} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
              ✕ Close
            </button>
          </div>
          <MasteryHeatmap data={allMastery[selected] || []} />
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs text-gray-500">
        {[
          ["#22c55e", "Strong 80%+"],
          ["#16a34a", "Good 60%+"],
          ["#ca8a04", "Average 40%+"],
          ["#ea580c", "Weak 20%+"],
          ["#dc2626", "Very Weak"],
          ["#374151", "No data"],
        ].map(([c, lbl]) => (
          <span key={lbl} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded inline-block" style={{ background: c }} />
            {lbl}
          </span>
        ))}
      </div>
    </div>
  );
}
