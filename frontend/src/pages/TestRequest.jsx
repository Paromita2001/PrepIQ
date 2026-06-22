import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { test as testApi, upload as uploadApi } from "../api/client";
import AgentTrace from "../components/AgentTrace";
import UploadModal from "../components/UploadModal";

const CBSE_SUBJECTS = ["Mathematics", "Science", "English", "Hindi", "Social Science", "Sanskrit"];

export default function TestRequest() {
  const nav = useNavigate();

  const [subject,          setSubject]          = useState("");     // "" = nothing selected
  const [prompt,           setPrompt]           = useState("");
  const [mode,             setMode]             = useState("practice");
  const [loading,          setLoading]          = useState(false);
  const [events,           setEvents]           = useState([]);
  const [err,              setErr]              = useState("");
  const [uploadedSubjects, setUploadedSubjects] = useState([]);    // [{name, has_book, has_pyq}]
  const [isUploaded,       setIsUploaded]       = useState(false); // selected from uploads?
  const [showUploadModal,  setShowUploadModal]  = useState(false);

  const loadUploadedSubjects = () => {
    uploadApi.subjects()
      .then((r) => setUploadedSubjects(r.data || []))
      .catch(() => {});
  };

  useEffect(() => { loadUploadedSubjects(); }, []);

  const selectSubject = (s, uploaded = false) => {
    setSubject(s);
    setIsUploaded(uploaded);
    setErr("");
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr("");

    if (!subject && !prompt.trim()) {
      setErr("Please select a subject or describe what you want to test in the prompt.");
      return;
    }

    setLoading(true);
    setEvents([]);

    try {
      let res;

      if (isUploaded) {
        // Fast path — skip multi-agent pipeline, serve uploaded PYQ questions directly
        setEvents(["Loading questions from your uploaded materials…"]);
        res = await uploadApi.generateTest(subject, mode);
      } else {
        // Full multi-agent pipeline
        const payload = {
          subject: subject || "",
          mode,
          raw_prompt: prompt || (subject ? `Test me on ${subject}` : ""),
        };
        setEvents(["Router: parsing request..."]);
        res = await testApi.generate(payload);
      }

      setEvents(res.data.events || []);
      sessionStorage.setItem("test_data", JSON.stringify(res.data));
      nav("/test/attempt");
    } catch (ex) {
      if (!ex.response) {
        const isTimeout = ex.code === "ECONNABORTED" || ex.message?.includes("timeout");
        setErr(
          isTimeout
            ? "Test generation timed out. Mock exams can take 3–5 minutes — try Practice mode for a faster test."
            : "Cannot reach the backend server. Make sure it is running on port 8000."
        );
      } else {
        const detail = ex.response?.data?.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
            ? detail.map((d) => d.msg).join("; ")
            : `Server error ${ex.response.status}`;
        setErr(msg);
      }
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-4 max-w-2xl mx-auto">
      <button
        onClick={() => nav("/dashboard")}
        className="text-gray-400 hover:text-gray-200 text-sm mb-6 flex items-center gap-1"
      >
        ← Dashboard
      </button>

      {/* Header row */}
      <div className="flex items-start justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold">Start a Test</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            Choose a subject or describe what you want to practise.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowUploadModal(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 hover:border-gray-500 transition-colors"
        >
          📤 Upload Material
        </button>
      </div>

      <form onSubmit={submit} className="space-y-5 mt-6">

        {/* ── CBSE subjects ── */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">CBSE Subjects</label>
          <div className="flex flex-wrap gap-2">
            {CBSE_SUBJECTS.map((s) => (
              <button
                type="button"
                key={s}
                onClick={() => selectSubject(s, false)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  subject === s && !isUploaded
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-300 hover:bg-gray-700"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* ── Uploaded subjects (purple) ── */}
        {uploadedSubjects.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">My Uploads</label>
            <div className="flex flex-wrap gap-2">
              {uploadedSubjects.map((s) => (
                <button
                  type="button"
                  key={s.name}
                  onClick={() => selectSubject(s.name, true)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
                    subject === s.name && isUploaded
                      ? "bg-purple-600 text-white"
                      : "bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 hover:border-gray-600"
                  }`}
                >
                  {s.has_pyq ? "📝" : "📚"} {s.name}
                  {s.has_book && s.has_pyq && (
                    <span className="text-xs opacity-60">+book</span>
                  )}
                </button>
              ))}
            </div>
            <p className="text-gray-600 text-xs mt-1.5">
              📝 = PYQ questions ready for testing · 📚 = book context for AI generation
            </p>
          </div>
        )}

        {/* Banner when an uploaded subject is selected */}
        {isUploaded && (
          <div className="bg-purple-950/40 border border-purple-800/50 rounded-lg px-4 py-3 text-sm text-purple-300">
            <strong>{subject}</strong> — test will use your uploaded previous-year questions directly.
            The prompt field below is not used for uploaded subjects.
          </div>
        )}

        {/* ── Prompt (only for CBSE subjects) ── */}
        {!isUploaded && (
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1.5">
              What do you want to test?{" "}
              <span className="text-gray-600 font-normal">(optional)</span>
            </label>
            <textarea
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-100 placeholder-gray-600 resize-none h-24 focus:outline-none focus:border-blue-500"
              placeholder={
                subject
                  ? `e.g. "Test me on Electricity and Ohm's Law, medium difficulty" or leave blank for adaptive test`
                  : `e.g. "Test me on Science for NEET" — subject will be detected from your prompt automatically`
              }
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>
        )}

        {/* ── Mode ── */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">Mode</label>
          <div className="flex gap-3">
            {[
              ["practice", "✏️ Practice",
                isUploaded ? "~15 questions from your uploads" : "Short adaptive test (~20 min)"],
              ["mock", "📋 Mock Exam",
                isUploaded ? "~25 questions from your uploads" : "Board pattern: A(20×1) + B(6×2) + C(7×3) + D(3×5) + E(3×4) = 80 marks"],
            ].map(([v, label, desc]) => (
              <button
                type="button"
                key={v}
                onClick={() => setMode(v)}
                className={`flex-1 rounded-lg p-3 text-left border transition-colors ${
                  mode === v
                    ? "border-blue-500 bg-blue-950"
                    : "border-gray-700 bg-gray-800 hover:border-gray-600"
                }`}
              >
                <div className="font-semibold text-sm">{label}</div>
                <div className="text-xs text-gray-400 mt-0.5">{desc}</div>
              </button>
            ))}
          </div>
        </div>

        {mode === "mock" && !isUploaded && (
          <div className="text-yellow-400 text-xs bg-yellow-950/40 border border-yellow-800/50 rounded-lg px-4 py-2.5">
            ⏳ Mock exams generate 39 questions across 5 sections — this takes{" "}
            <strong>3–5 minutes</strong>. Do not close the tab.
          </div>
        )}

        {err && (
          <div className="text-red-400 text-sm bg-red-950 border border-red-800 rounded-lg px-4 py-3">
            {err}
          </div>
        )}

        <button
          className="w-full py-3 rounded-lg text-base font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-50"
          disabled={loading}
        >
          {loading
            ? isUploaded
              ? "⚡ Loading your questions…"
              : mode === "mock"
              ? "🤖 Building mock exam…"
              : "🤖 Agents working…"
            : "Generate Test →"}
        </button>
      </form>

      {loading && (
        <div className="mt-4 text-center">
          <div className="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      <AgentTrace events={events} />

      {/* Nudge when no uploads yet */}
      {uploadedSubjects.length === 0 && (
        <div className="mt-8 border border-gray-800 rounded-xl p-4 text-center">
          <p className="text-gray-500 text-sm mb-2">
            Preparing for NEET, JEE, or any other exam?
          </p>
          <button
            type="button"
            onClick={() => setShowUploadModal(true)}
            className="text-blue-400 hover:text-blue-300 text-sm underline"
          >
            Upload your books or previous year papers →
          </button>
        </div>
      )}

      {showUploadModal && (
        <UploadModal
          onClose={() => setShowUploadModal(false)}
          onSuccess={loadUploadedSubjects}
        />
      )}
    </div>
  );
}
