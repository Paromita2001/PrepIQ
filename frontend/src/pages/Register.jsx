import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", board: "CBSE", exam_date: "" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await register({ ...form, exam_date: form.exam_date || null });
      nav("/dashboard");
    } catch (ex) {
      setErr(ex.response?.data?.detail || "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  const f = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold text-center mb-2">🎓 PrepIQ</h1>
        <p className="text-gray-400 text-center mb-8">Create your free account</p>
        <div className="card">
          <h2 className="text-xl font-semibold mb-6">Register</h2>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Full Name</label>
              <input className="input" placeholder="Rahul Sharma" value={form.name} onChange={f("name")} required />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" placeholder="you@example.com" value={form.email} onChange={f("email")} required />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input" type="password" placeholder="Min 6 characters" value={form.password} onChange={f("password")} required minLength={6} />
            </div>
            <div>
              <label className="label">Board</label>
              <select className="input" value={form.board} onChange={f("board")}>
                <option>CBSE</option>
                <option>ICSE</option>
              </select>
            </div>
            <div>
              <label className="label">Exam Date (optional)</label>
              <input className="input" type="date" value={form.exam_date} onChange={f("exam_date")} />
            </div>
            {err && <p className="text-red-400 text-sm">{err}</p>}
            <button className="btn-primary w-full" disabled={loading}>
              {loading ? "Creating account..." : "Create Account"}
            </button>
          </form>
          <p className="text-center text-gray-500 text-sm mt-4">
            Already registered? <Link to="/login" className="text-blue-400 hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
