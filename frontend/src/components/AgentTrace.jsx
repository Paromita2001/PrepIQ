const ICONS = {
  Router: "🔍",
  Research: "📊",
  Planner: "📋",
  Examiner: "📝",
  Evaluator: "⚖️",
  Mastery: "🧠",
  Mentor: "💡",
  done: "✅",
};

export default function AgentTrace({ events = [] }) {
  if (!events.length) return null;
  return (
    <div className="card mt-4">
      <h3 className="text-sm font-semibold text-gray-400 mb-3">Agent pipeline</h3>
      <div className="space-y-2">
        {events.map((ev, i) => {
          const key = Object.keys(ICONS).find((k) => ev.includes(k)) || "";
          return (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="w-6 text-center">{ICONS[key] || "→"}</span>
              <span className="text-gray-300">{ev}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
