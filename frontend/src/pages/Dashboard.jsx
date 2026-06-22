import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { student as studentApi } from "../api/client";
import SubjectCharts from "../components/SubjectCharts";

const SUBJECTS = ["English", "Mathematics", "Science", "Social Science", "Hindi", "Sanskrit"];

function avgMastery(topicRows) {
  if (!topicRows || !topicRows.length) return undefined;
  const tested = topicRows.filter(r => r.mastery !== null && r.mastery !== undefined);
  if (!tested.length) return undefined;
  return tested.reduce((s, r) => s + r.mastery, 0) / tested.length;
}

export default function Dashboard() {
  const { student, logout } = useAuth();
  const nav = useNavigate();
  const [allMastery, setAllMastery]   = useState({});
  const [subjectAvg, setSubjectAvg]   = useState({});
  const [sessions,   setSessions]     = useState([]);
  const [loading,    setLoading]      = useState(true);
  const [err,        setErr]          = useState("");
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting,        setDeleting]        = useState(false);
  const [deleteErr,       setDeleteErr]       = useState("");

  const loadData = useCallback(() => {
    setLoading(true);
    setErr("");
    Promise.all([
      ...SUBJECTS.map(s => studentApi.mastery(s).then(r => ({ subject: s, data: r.data })).catch(() => ({ subject: s, data: [] }))),
      studentApi.sessions().then(r => r.data).catch(() => []),
    ]).then(results => {
      const sessionsData = results[results.length - 1];
      const masteryResults = results.slice(0, SUBJECTS.length);

      const masteryMap = {};
      const avgMap = {};
      for (const { subject, data } of masteryResults) {
        masteryMap[subject] = data;
        avgMap[subject] = avgMastery(data);
      }

      setAllMastery(masteryMap);
      setSubjectAvg(avgMap);
      setSessions(Array.isArray(sessionsData) ? sessionsData : []);
    }).catch(() => {
      setErr("Failed to load data. Check your connection.");
    }).finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDeleteAll = async () => {
    setDeleting(true);
    setDeleteErr("");
    try {
      await studentApi.deleteAllTests();
      setShowDeleteModal(false);
      loadData();
    } catch {
      setDeleteErr("Failed to delete. Please try again.");
    } finally {
      setDeleting(false);
    }
  };

  const daysLeft = student?.exam_date
    ? Math.max(0, Math.ceil((new Date(student.exam_date) - new Date()) / 86400000))
    : null;

  return (
    <div className="min-h-screen p-4 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">👋 Hi, {student?.name?.split(" ")[0] || "Topper"}! 🏆</h1>
          {daysLeft !== null && (
            <p className="text-gray-400 text-sm mt-0.5">
              {daysLeft} days to exam · {student.board}
            </p>
          )}
        </div>
        <div className="flex gap-3">
          <button className="btn-primary" onClick={() => nav("/test")}>
            ✏️ Start Test
          </button>
          {sessions.length > 0 && (
            <button
              className="btn-secondary text-red-400 hover:text-red-300 border-red-900 hover:border-red-700"
              onClick={() => { setDeleteErr(""); setShowDeleteModal(true); }}
            >
              🗑️ Delete All Tests
            </button>
          )}
          <button className="btn-secondary" onClick={logout}>Logout</button>
        </div>
      </div>

      {/* Recent sessions */}
      {sessions.length > 0 && (
        <div className="card mb-6 overflow-x-auto">
          <h2 className="font-semibold text-gray-200 mb-3">Recent Tests</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase tracking-wide border-b border-gray-800">
                <th className="text-left pb-2 pr-4">Date</th>
                <th className="text-left pb-2 pr-4">Subject</th>
                <th className="text-left pb-2 pr-4">Chapters</th>
                <th className="text-left pb-2 pr-4">Mode</th>
                <th className="text-right pb-2">Score / Grade</th>
              </tr>
            </thead>
            <tbody>
              {sessions.slice(0, 8).map((s) => {
                const gradeColor = {
                  A1: "text-green-400", A2: "text-green-400",
                  B1: "text-blue-400",  B2: "text-blue-400",
                  C1: "text-yellow-400",C2: "text-yellow-400",
                  D: "text-orange-400", E: "text-red-400",
                }[s.grade] || "text-gray-400";
                return (
                  <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                    <td className="py-2.5 pr-4 text-gray-400 whitespace-nowrap">
                      {new Date(s.started_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-200 font-medium whitespace-nowrap">
                      {s.subject_name || "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-400 max-w-[200px] truncate" title={s.chapters}>
                      {s.chapters || <span className="text-gray-600 italic">—</span>}
                    </td>
                    <td className="py-2.5 pr-4">
                      <span className={`text-xs px-2 py-0.5 rounded capitalize ${s.mode === "mock" ? "bg-purple-950 text-purple-300" : "bg-gray-800 text-gray-400"}`}>
                        {s.mode}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      {s.total_score !== null && s.total_score !== undefined ? (
                        <span className="font-semibold">
                          <span className="text-gray-200">{s.total_score}/{s.total_marks}</span>
                          <span className={`ml-2 font-bold ${gradeColor}`}>{s.grade}</span>
                        </span>
                      ) : (
                        <span className="text-gray-600 italic text-xs">Incomplete</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {err && (
        <p className="text-red-400 text-sm mb-4 bg-red-950 border border-red-800 rounded-lg px-4 py-3">{err}</p>
      )}

      {/* Subject charts */}
      <div className="mb-4">
        <h2 className="font-semibold text-gray-200 mb-4">Performance Overview</h2>
        {loading ? (
          <div className="text-center text-gray-500 py-10">Loading...</div>
        ) : (
          <SubjectCharts
            subjectAvg={subjectAvg}
            allMastery={allMastery}
            sessions={sessions}
          />
        )}
      </div>

      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-sm w-full shadow-2xl">
            <h3 className="text-lg font-semibold text-gray-100 mb-2">Delete all tests?</h3>
            <p className="text-gray-400 text-sm mb-4">
              This will permanently delete all your test sessions, answers, and mastery progress.
              This cannot be undone.
            </p>
            {deleteErr && (
              <p className="text-red-400 text-sm mb-3 bg-red-950 border border-red-800 rounded px-3 py-2">
                {deleteErr}
              </p>
            )}
            <div className="flex gap-3 justify-end">
              <button
                className="btn-secondary"
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-white font-medium text-sm transition-colors disabled:opacity-50"
                onClick={handleDeleteAll}
                disabled={deleting}
              >
                {deleting ? "Deleting…" : "Yes, delete all"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
