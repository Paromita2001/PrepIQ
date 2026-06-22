import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AgentTrace from "../components/AgentTrace";

function ScoreBadge({ score, max }) {
  const pct = max ? Math.round(score / max * 100) : 0;
  const cls = pct >= 70 ? "text-green-400 bg-green-950 border-green-800" : pct >= 40 ? "text-yellow-400 bg-yellow-950 border-yellow-800" : "text-red-400 bg-red-950 border-red-800";
  return (
    <span className={`text-sm font-bold px-2.5 py-0.5 rounded border ${cls}`}>
      {score}/{max} ({pct}%)
    </span>
  );
}

export default function Results() {
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [open, setOpen] = useState({});

  useEffect(() => {
    const raw = sessionStorage.getItem("result_data");
    if (!raw) { nav("/dashboard"); return; }
    setData(JSON.parse(raw));
    sessionStorage.removeItem("result_data");
  }, []);

  if (!data) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading results...</div>;

  const { total_score, total_marks, percentage, eval_results = [], mentor_advice, events = [] } = data;
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }));

  return (
    <div className="min-h-screen p-4 max-w-3xl mx-auto">
      <button onClick={() => nav("/dashboard")} className="text-gray-400 hover:text-gray-200 text-sm mb-6 flex items-center gap-1">← Dashboard</button>

      {/* Summary */}
      <div className="card mb-6 text-center">
        <div className={`text-5xl font-bold mb-1 ${percentage >= 70 ? "text-green-400" : percentage >= 40 ? "text-yellow-400" : "text-red-400"}`}>
          {percentage}%
        </div>
        <div className="text-gray-400 text-sm">{total_score} / {total_marks} marks</div>
        <div className="text-gray-500 text-xs mt-1">
          {percentage >= 70 ? "🎉 Excellent performance!" : percentage >= 40 ? "📈 Good effort — review weak areas." : "📖 Focus on fundamentals."}
        </div>
      </div>

      {/* Mentor advice */}
      {mentor_advice && (
        <div className="card mb-6 border-blue-800 bg-blue-950/20">
          <h2 className="font-semibold text-blue-300 mb-4">💡 Mentor Advice</h2>

          {/* Study plan summary */}
          <p className="text-gray-200 text-sm mb-4 leading-relaxed">{mentor_advice.study_plan_summary}</p>

          {/* Chapter recommendations */}
          {mentor_advice.recommendations?.length > 0 && (
            <div className="mb-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">What to do next</p>
              <ul className="space-y-2">
                {mentor_advice.recommendations.map((r, i) => (
                  <li key={i} className="text-sm text-gray-300 flex gap-2.5 bg-gray-800/60 rounded-lg px-3 py-2">
                    <span className="text-blue-400 shrink-0">→</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Strong / Weak topic chips */}
          <div className="grid grid-cols-2 gap-4 pt-3 border-t border-gray-800">
            {mentor_advice.strong_topics?.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1.5">✅ Strong topics</p>
                <div className="flex flex-wrap gap-1">
                  {mentor_advice.strong_topics.map((t) => (
                    <span key={t} className="text-xs bg-green-900/60 text-green-300 border border-green-800 px-2 py-0.5 rounded">{t}</span>
                  ))}
                </div>
              </div>
            )}
            {mentor_advice.weak_topics?.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1.5">⚠️ Needs revision</p>
                <div className="flex flex-wrap gap-1">
                  {mentor_advice.weak_topics.map((t) => (
                    <span key={t} className="text-xs bg-red-900/60 text-red-300 border border-red-800 px-2 py-0.5 rounded">{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Per-question breakdown */}
      <h2 className="font-semibold text-gray-200 mb-3">Question Breakdown</h2>
      <div className="space-y-3 mb-6">
        {eval_results.map((r, i) => (
          <div key={r.question_id} className="card">
            <div className="flex items-center justify-between cursor-pointer" onClick={() => toggle(r.question_id)}>
              <span className="font-medium text-sm">Question {i + 1}</span>
              <div className="flex items-center gap-3">
                <ScoreBadge score={r.score} max={r.max_score} />
                <span className="text-gray-500 text-xs">{open[r.question_id] ? "▲" : "▼"}</span>
              </div>
            </div>

            {open[r.question_id] && (
              <div className="mt-4 space-y-3 text-sm">
                {r.awarded_points?.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Points awarded</p>
                    {r.awarded_points.map((p, j) => (
                      <div key={j} className={`flex items-start gap-2 ${p.awarded ? "text-green-300" : "text-gray-500"}`}>
                        <span>{p.awarded ? "✓" : "✗"}</span>
                        <span>{p.point} (+{p.marks})</span>
                      </div>
                    ))}
                  </div>
                )}
                {r.missing_points?.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Missing points</p>
                    {r.missing_points.map((p, j) => (
                      <div key={j} className="text-red-300 flex items-start gap-2"><span>✗</span><span>{p}</span></div>
                    ))}
                  </div>
                )}
                {r.citation && (
                  <div className="bg-gray-800 rounded-lg p-3 text-xs text-gray-400 border-l-2 border-blue-500">
                    📌 {r.citation}
                  </div>
                )}
                {r.feedback && <p className="text-gray-300 italic text-xs">{r.feedback}</p>}
              </div>
            )}
          </div>
        ))}
      </div>

      <AgentTrace events={events} />

      <div className="flex gap-3 mt-6">
        <button className="btn-primary flex-1" onClick={() => nav("/test")}>Take Another Test</button>
        <button className="btn-secondary flex-1" onClick={() => nav("/dashboard")}>Dashboard</button>
      </div>
    </div>
  );
}
