import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { test as testApi } from "../api/client";
import MathToolbar from "../components/MathToolbar";
import DrawingCanvas from "../components/DrawingCanvas";

function Timer({ limitMinutes, onExpire }) {
  const [secs, setSecs] = useState(limitMinutes * 60);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    const id = setInterval(() => {
      setSecs((s) => {
        if (s <= 1) { clearInterval(id); onExpireRef.current(); return 0; }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const m = Math.floor(secs / 60).toString().padStart(2, "0");
  const s = (secs % 60).toString().padStart(2, "0");
  const danger = secs < 300;
  return (
    <span className={`font-mono font-bold ${danger ? "text-red-400" : "text-gray-300"}`}>
      ⏱ {m}:{s}
    </span>
  );
}

/**
 * Parse MCQ options embedded in question text.
 * Expects lines like: "(A) Option text" anywhere after the question stem.
 * Returns { stem, options: [{key:"A", text:"Option text"}, ...] }
 * If no options found, returns { stem: fullText, options: [] }
 */
function parseMcqOptions(text) {
  // Match (A), (B), (C), (D) — case-insensitive, anywhere in text
  const optionRegex = /\(([A-Da-d])\)\s*([^\n(]+)/g;
  const options = [];
  let match;
  while ((match = optionRegex.exec(text)) !== null) {
    options.push({ key: match[1].toUpperCase(), text: match[2].trim() });
  }
  if (options.length < 2) return { stem: text, options: [] };
  // Stem = everything before the first option marker
  const firstMarker = text.search(/\([A-Da-d]\)/);
  const stem = firstMarker > 0 ? text.slice(0, firstMarker).trim() : text;
  return { stem, options };
}

// Section label metadata for mock exam display
const SECTION_LABELS = {
  A: "Section A — Multiple Choice (1 mark each)",
  B: "Section B — Very Short Answer (2 marks each)",
  C: "Section C — Short Answer (3 marks each)",
  D: "Section D — Long Answer (5 marks each)",
  E: "Section E — Short Answer (4 marks each)",
};

// Agent steps shown during submission loading overlay
const SUBMIT_STEPS = [
  { label: "Evaluating answers...", duration: 0 },
  { label: "Grading marks & feedback...", duration: 8000 },
  { label: "Updating your mastery profile...", duration: 16000 },
  { label: "Mentor analysing weak areas...", duration: 22000 },
  { label: "Preparing results...", duration: 28000 },
];

export default function TestAttempt() {
  const nav = useNavigate();
  const [testData, setTestData] = useState(null);
  const [answers, setAnswers] = useState({});
  const [current, setCurrent] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitStep, setSubmitStep] = useState(0);
  // ocrLoading: null | { qid, page, total }
  const [ocrLoading, setOcrLoading] = useState(null);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [drawings, setDrawings] = useState({});      // questionId → base64 PNG
  const [showMathBar, setShowMathBar] = useState(false);
  const [showCanvas,  setShowCanvas]  = useState(false);
  const fileRef     = useRef();
  const textareaRef = useRef();                       // for MathToolbar cursor insert
  const submitTimers = useRef([]);

  useEffect(() => {
    const raw = sessionStorage.getItem("test_data");
    if (!raw) { nav("/test"); return; }
    const data = JSON.parse(raw);
    setTestData(data);
    const init = {};
    data.questions.forEach((q) => { init[q.id] = ""; });
    setAnswers(init);
  }, []);

  const submit = async () => {
    setSubmitting(true);
    setSubmitStep(0);
    // Schedule step label advances — purely visual feedback while backend runs
    submitTimers.current.forEach(clearTimeout);
    submitTimers.current = SUBMIT_STEPS.slice(1).map((step, i) =>
      setTimeout(() => setSubmitStep(i + 1), step.duration)
    );
    try {
      const strAnswers = {};
      Object.entries(answers).forEach(([k, v]) => { strAnswers[k] = v; });
      const res = await testApi.submit(testData.session_id, strAnswers);
      submitTimers.current.forEach(clearTimeout);
      sessionStorage.setItem("result_data", JSON.stringify(res.data));
      sessionStorage.setItem("drawing_data", JSON.stringify(drawings));
      nav("/test/results");
    } catch (ex) {
      submitTimers.current.forEach(clearTimeout);
      const detail = ex.response?.data?.detail || ex.message || "Unknown error";
      alert("Submission failed: " + detail + "\n\nTip: Make sure the backend is running on port 8000.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpload = async (questionId, files) => {
    const pages = Array.from(files).slice(0, 10);
    if (Array.from(files).length > 10) {
      alert("Maximum 10 pages allowed. Only the first 10 will be uploaded.");
    }
    if (!pages.length) return;

    const errors = [];
    for (let i = 0; i < pages.length; i++) {
      setOcrLoading({ qid: questionId, page: i + 1, total: pages.length });
      try {
        const res = await testApi.uploadAnswer(questionId, pages[i]);
        const text = (res.data.extracted_text || "").trim();
        if (text && !text.startsWith("OCR unavailable") && !text.startsWith("OCR error") && !text.startsWith("Could not")) {
          setAnswers((a) => {
            const prev = a[questionId] || "";
            return { ...a, [questionId]: prev ? prev + "\n\n" + text : text };
          });
        } else if (text) {
          errors.push(`Page ${i + 1}: ${text}`);
        }
      } catch {
        errors.push(`Page ${i + 1}: upload failed`);
      }
    }

    setOcrLoading(null);
    // Reset so the same file(s) can be re-selected if needed
    if (fileRef.current) fileRef.current.value = "";

    if (errors.length) alert(errors.join("\n"));
  };

  if (!testData) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading test...</div>;

  const questions = testData.questions || [];
  const q = questions[current];
  const answered = Object.values(answers).filter(Boolean).length;
  const plan = testData.plan;
  const isMock = plan?.mode === "mock";
  const isScienceMath = ["Mathematics", "Science"].includes(plan?.subject);

  // Build section groups for mock exam navigation
  // questions have a `section` field; group them by section preserving order
  const sectionGroups = isMock ? (() => {
    const groups = {};
    const order = [];
    questions.forEach((qq, idx) => {
      const sec = qq.section || "";
      if (sec && !groups[sec]) {
        groups[sec] = [];
        order.push(sec);
      }
      if (sec) groups[sec].push({ ...qq, _idx: idx });
    });
    return { groups, order };
  })() : null;

  return (
    <div className="min-h-screen p-4 max-w-3xl mx-auto">
      {/* Exit confirmation modal */}
      {showExitConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 max-w-sm w-full text-center shadow-2xl">
            <div className="text-3xl mb-3">⚠️</div>
            <h2 className="text-lg font-bold mb-2">Exit Test?</h2>
            <p className="text-gray-400 text-sm mb-5">
              Your answers will be lost. This test session will be marked incomplete.
            </p>
            <div className="flex gap-3">
              <button
                className="flex-1 btn-secondary"
                onClick={() => setShowExitConfirm(false)}
              >
                Keep Going
              </button>
              <button
                className="flex-1 px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-white font-medium transition-colors"
                onClick={() => { sessionStorage.removeItem("test_data"); nav("/test"); }}
              >
                Exit Test
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Submit loading overlay */}
      {submitting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-8 max-w-sm w-full text-center shadow-2xl">
            <div className="text-3xl mb-4 animate-spin">⚙️</div>
            <h2 className="text-lg font-bold mb-2">Evaluating your test</h2>
            <p className="text-gray-400 text-sm mb-5">AI agents are analysing your answers…</p>
            <div className="space-y-2">
              {SUBMIT_STEPS.map((step, i) => (
                <div key={i} className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all ${i < submitStep ? "text-green-400 bg-green-950/40" : i === submitStep ? "text-white bg-blue-900/50 font-medium" : "text-gray-600"}`}>
                  <span>{i < submitStep ? "✓" : i === submitStep ? "▶" : "○"}</span>
                  <span>{step.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold">{plan?.subject} — {isMock ? "Mock Exam" : "Practice Test"}</h1>
          <p className="text-gray-400 text-sm">{answered}/{questions.length} answered</p>
        </div>
        <div className="flex items-center gap-3">
          {plan && <Timer limitMinutes={plan.time_limit_minutes} onExpire={submit} />}
          <button
            onClick={() => setShowExitConfirm(true)}
            className="text-xs px-3 py-1.5 rounded-lg bg-gray-800 text-gray-400 hover:bg-red-900 hover:text-red-300 transition-colors border border-gray-700"
          >
            ✕ Exit
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-gray-800 rounded-full mb-6">
        <div className="h-1.5 bg-blue-500 rounded-full transition-all" style={{ width: `${(answered / questions.length) * 100}%` }} />
      </div>

      {/* Question nav — grouped by section for mock exams */}
      {isMock && sectionGroups ? (
        <div className="mb-5 space-y-3">
          {sectionGroups.order.map((sec) => (
            <div key={sec}>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1.5">
                {SECTION_LABELS[sec] || `Section ${sec}`}
              </p>
              <div className="flex flex-wrap gap-2">
                {sectionGroups.groups[sec].map(({ _idx, id }) => (
                  <button
                    key={id}
                    onClick={() => setCurrent(_idx)}
                    className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${_idx === current ? "bg-blue-600 text-white" : answers[id] ? "bg-green-800 text-green-200" : "bg-gray-800 text-gray-400"}`}
                  >
                    {_idx + 1}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 mb-5">
          {questions.map((qq, i) => (
            <button
              key={qq.id}
              onClick={() => setCurrent(i)}
              className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${i === current ? "bg-blue-600 text-white" : answers[qq.id] ? "bg-green-800 text-green-200" : "bg-gray-800 text-gray-400"}`}
            >
              {i + 1}
            </button>
          ))}
        </div>
      )}

      {/* Section header above current question for mock exams */}
      {isMock && q?.section && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700">
          <p className="text-xs font-semibold text-blue-400 uppercase tracking-wide">
            {SECTION_LABELS[q.section] || `Section ${q.section}`}
          </p>
        </div>
      )}

      {/* Current question */}
      {q && (
        <div className="card mb-5">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">{q.topic_name} · {q.chapter_name}</span>
              <div className="flex gap-2 mt-1">
                <span className="text-xs bg-gray-800 px-2 py-0.5 rounded">{q.marks} mark{q.marks > 1 ? "s" : ""}</span>
                <span className="text-xs bg-gray-800 px-2 py-0.5 rounded capitalize">{q.type}</span>
                <span className="text-xs bg-gray-800 px-2 py-0.5 rounded">Difficulty {q.difficulty}/5</span>
                {isMock && q.section && (
                  <span className="text-xs bg-blue-900 text-blue-300 px-2 py-0.5 rounded">Sec {q.section}</span>
                )}
                {q.source && q.source.startsWith("pyq-") && (
                  <span className="text-xs bg-yellow-900 text-yellow-300 px-2 py-0.5 rounded font-semibold">
                    📅 PYQ {q.source.replace("pyq-", "")}
                  </span>
                )}
              </div>
            </div>
            <span className="text-gray-500 text-sm shrink-0">Q{current + 1}/{questions.length}</span>
          </div>
          {(() => {
            const parsed = q.type === "mcq" ? parseMcqOptions(q.text) : null;
            const stem = parsed ? parsed.stem : q.text;
            return (
              <>
                <p className="text-gray-100 leading-relaxed mb-3">{stem}</p>
                {q.source && q.source.startsWith("pyq-") && (
                  <p className="text-xs text-yellow-500 mb-3 italic">
                    ★ This question appeared in CBSE Board Exam {q.source.replace("pyq-", "")}
                  </p>
                )}
              </>
            );
          })()}

          {/* Answer area */}
          {q.type === "mcq" ? (
            <div className="space-y-2">
              {(() => {
                const { options } = parseMcqOptions(q.text);
                // If LLM embedded real options, show them; otherwise show blank A/B/C/D
                const displayOpts = options.length >= 2
                  ? options
                  : ["A", "B", "C", "D"].map((k) => ({ key: k, text: "" }));
                return displayOpts.map(({ key, text }) => (
                  <button
                    key={key}
                    onClick={() => setAnswers((a) => ({ ...a, [q.id]: `(${key})` }))}
                    className={`w-full text-left px-4 py-2.5 rounded-lg text-sm transition-colors border ${answers[q.id] === `(${key})` ? "border-blue-500 bg-blue-950 text-blue-200" : "border-gray-700 bg-gray-800 hover:border-gray-600"}`}
                  >
                    <span className="font-semibold text-gray-400 mr-2">({key})</span>
                    {text || <span className="text-gray-600 italic">—</span>}
                  </button>
                ));
              })()}
              <p className="text-xs text-gray-500 mt-1">Or type your full answer below:</p>
              <textarea
                className="input h-20 resize-none"
                placeholder="Type your MCQ answer..."
                value={answers[q.id] || ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
              />
            </div>
          ) : (
            <div className="space-y-3">
              {/* Maths / Science tool toggles */}
              {isScienceMath && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowMathBar((v) => !v)}
                    className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors ${
                      showMathBar
                        ? "bg-blue-900 border-blue-600 text-blue-200"
                        : "bg-gray-800 border-gray-700 text-gray-400 hover:border-blue-700 hover:text-blue-300"
                    }`}
                  >
                    ∑ Math Symbols
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCanvas((v) => !v)}
                    className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors ${
                      showCanvas
                        ? "bg-purple-900 border-purple-600 text-purple-200"
                        : "bg-gray-800 border-gray-700 text-gray-400 hover:border-purple-700 hover:text-purple-300"
                    }`}
                  >
                    📐 Draw Diagram
                  </button>
                  {drawings[q.id] && (
                    <span className="text-xs text-purple-400 self-center">✓ diagram saved</span>
                  )}
                </div>
              )}

              {/* Math symbol toolbar */}
              {isScienceMath && showMathBar && (
                <MathToolbar
                  textareaRef={textareaRef}
                  value={answers[q.id] || ""}
                  onChange={(val) => setAnswers((a) => ({ ...a, [q.id]: val }))}
                />
              )}

              <textarea
                ref={textareaRef}
                className="input h-36 resize-y"
                placeholder="Type your answer here…"
                value={answers[q.id] || ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
              />

              {/* Drawing canvas */}
              {isScienceMath && showCanvas && (
                <DrawingCanvas
                  key={q.id}
                  initialData={drawings[q.id] || null}
                  onChange={(data) =>
                    setDrawings((d) => ({ ...d, [q.id]: data }))
                  }
                />
              )}

              <div className="flex items-center gap-3 flex-wrap">
                <button
                  type="button"
                  className="btn-secondary text-sm py-2"
                  onClick={() => fileRef.current?.click()}
                  disabled={ocrLoading?.qid === q.id}
                >
                  {ocrLoading?.qid === q.id
                    ? `Scanning page ${ocrLoading.page}/${ocrLoading.total}...`
                    : "📷 Upload Handwritten"}
                </button>
                <input
                  type="file"
                  ref={fileRef}
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => e.target.files.length && handleUpload(q.id, e.target.files)}
                />
                <span className="text-xs text-gray-500">
                  Select multiple images for multi-page answers — text appends automatically
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button className="btn-secondary" onClick={() => setCurrent((c) => Math.max(0, c - 1))} disabled={current === 0}>← Prev</button>
        {current < questions.length - 1 ? (
          <button className="btn-primary" onClick={() => setCurrent((c) => c + 1)}>Next →</button>
        ) : (
          <button className="btn-primary bg-green-600 hover:bg-green-500" onClick={submit} disabled={submitting}>
            {submitting ? "Submitting..." : "Submit Test ✓"}
          </button>
        )}
      </div>
    </div>
  );
}
