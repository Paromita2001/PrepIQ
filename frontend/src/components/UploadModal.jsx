import { useState, useRef } from "react";
import { upload as uploadApi } from "../api/client";

export default function UploadModal({ onClose, onSuccess }) {
  const [file,      setFile]      = useState(null);
  const [subject,   setSubject]   = useState("");
  const [docType,   setDocType]   = useState("pyq");
  const [uploading, setUploading] = useState(false);
  const [done,      setDone]      = useState(false);
  const [err,       setErr]       = useState("");
  const fileRef = useRef();

  const pickFile = (f) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setErr("Only PDF files are supported."); return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setErr("File too large — max 20 MB."); return;
    }
    setErr("");
    setFile(f);
  };

  const submit = async () => {
    if (!file)           { setErr("Please select a PDF file."); return; }
    if (!subject.trim()) { setErr("Please enter a subject / exam name."); return; }
    setErr("");
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("subject_name", subject.trim());
      form.append("doc_type", docType);
      await uploadApi.uploadDocument(form);
      setDone(true);
      setTimeout(() => { onSuccess?.(); onClose(); }, 2500);
    } catch (ex) {
      const detail = ex.response?.data?.detail;
      setErr(typeof detail === "string" ? detail : "Upload failed — please try again.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-lg w-full shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-100">Upload Study Material</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-2xl leading-none">×</button>
        </div>

        {done ? (
          <div className="text-center py-8">
            <div className="text-5xl mb-3">✅</div>
            <p className="text-green-400 font-semibold text-lg">Uploaded successfully!</p>
            <p className="text-gray-400 text-sm mt-2">
              Processing in the background (1–3 min).<br />
              The subject will appear in <strong>My Uploads</strong> once ready.
            </p>
          </div>
        ) : (
          <>
            {/* Drop zone */}
            <div
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer mb-5 transition-colors select-none ${
                file ? "border-blue-500 bg-blue-950/20" : "border-gray-700 hover:border-gray-500"
              }`}
              onDrop={(e) => { e.preventDefault(); pickFile(e.dataTransfer.files[0]); }}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => pickFile(e.target.files[0])}
              />
              {file ? (
                <>
                  <div className="text-3xl mb-1">📄</div>
                  <p className="text-blue-300 font-medium text-sm break-all">{file.name}</p>
                  <p className="text-gray-500 text-xs mt-0.5">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                    <span
                      className="ml-2 text-gray-600 underline cursor-pointer hover:text-gray-400"
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    >
                      change
                    </span>
                  </p>
                </>
              ) : (
                <>
                  <div className="text-3xl mb-2 text-gray-600">📁</div>
                  <p className="text-gray-400 text-sm">Click or drag & drop a PDF here</p>
                  <p className="text-gray-600 text-xs mt-1">Max 20 MB · PDF only</p>
                </>
              )}
            </div>

            {/* Subject name — completely free text, no presets */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-1.5">
                Subject / Exam Name <span className="text-red-400">*</span>
              </label>
              <input
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
                placeholder="Enter subject or exam name"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
              <p className="text-gray-600 text-xs mt-1">
                This name will appear as a button in Start Test.
              </p>
            </div>

            {/* Type selector */}
            <div className="mb-5">
              <label className="block text-sm text-gray-400 mb-2">What type of material is this?</label>
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["pyq", "📝 Previous Year Questions",
                    "Questions are extracted and added to your personal test bank"],
                  ["book", "📚 Study Book / Notes",
                    "Content is used as AI context when generating new questions"],
                ].map(([val, label, desc]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setDocType(val)}
                    className={`rounded-xl p-3 text-left border transition-colors ${
                      docType === val
                        ? "border-blue-500 bg-blue-950"
                        : "border-gray-700 bg-gray-800 hover:border-gray-600"
                    }`}
                  >
                    <div className="font-medium text-sm text-gray-200">{label}</div>
                    <div className="text-xs text-gray-500 mt-1 leading-relaxed">{desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {err && (
              <p className="text-red-400 text-sm mb-4 bg-red-950 border border-red-800 rounded-lg px-3 py-2">
                {err}
              </p>
            )}

            <div className="flex gap-3 justify-end">
              <button
                className="px-4 py-2 rounded-lg text-sm bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors"
                onClick={onClose}
                disabled={uploading}
              >
                Cancel
              </button>
              <button
                className="px-4 py-2 rounded-lg text-sm bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors disabled:opacity-50"
                onClick={submit}
                disabled={uploading}
              >
                {uploading ? "Uploading…" : "Upload →"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
