function masteryColor(m) {
  if (m === undefined || m === null) return "bg-gray-800";
  if (m >= 0.8) return "bg-green-500";
  if (m >= 0.6) return "bg-green-700";
  if (m >= 0.4) return "bg-yellow-600";
  if (m >= 0.2) return "bg-orange-600";
  return "bg-red-700";
}

function masteryLabel(m) {
  if (m === undefined || m === null) return "Untested";
  if (m >= 0.8) return "Strong";
  if (m >= 0.6) return "Good";
  if (m >= 0.4) return "Average";
  if (m >= 0.2) return "Weak";
  return "Very Weak";
}

export default function MasteryHeatmap({ data = [] }) {
  if (!data.length)
    return (
      <div className="card text-center text-gray-500 py-10">
        No mastery data yet — complete a test to see your heatmap.
      </div>
    );

  const byChapter = data.reduce((acc, row) => {
    if (!acc[row.chapter_name]) acc[row.chapter_name] = [];
    acc[row.chapter_name].push(row);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      {Object.entries(byChapter).map(([chapter, topics]) => (
        <div key={chapter} className="card">
          <h3 className="font-semibold text-gray-200 mb-3">{chapter}</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {topics.map((t) => (
              <div
                key={t.topic_id}
                className={`${masteryColor(t.mastery)} rounded-lg p-2.5 text-xs`}
                title={`Mastery: ${(t.mastery * 100).toFixed(0)}% | Attempts: ${t.attempts}`}
              >
                <div className="font-medium text-white text-xs leading-tight">{t.topic_name}</div>
                <div className="text-white/70 mt-0.5">
                  {masteryLabel(t.mastery)} · {(t.mastery * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="flex flex-wrap gap-3 text-xs text-gray-400">
        {[["bg-green-500","Strong 80%+"],["bg-green-700","Good 60%+"],["bg-yellow-600","Average 40%+"],["bg-orange-600","Weak 20%+"],["bg-red-700","Very Weak"]].map(([cls, lbl]) => (
          <span key={lbl} className="flex items-center gap-1.5">
            <span className={`w-3 h-3 rounded ${cls} inline-block`} />{lbl}
          </span>
        ))}
      </div>
    </div>
  );
}
