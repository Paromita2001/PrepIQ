import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

export const auth = {
  register: (data) => api.post("/auth/register", data),
  login: (data) => api.post("/auth/login", data),
  me: () => api.get("/auth/me"),
};

export const student = {
  subjects: () => api.get("/student/subjects"),
  mastery: (subject) => api.get(`/student/mastery/${subject}`),
  sessions: () => api.get("/student/sessions"),
  deleteAllTests: () => api.delete("/student/tests"),
};

export const test = {
  generate: (payload) => api.post("/test/generate", payload, { timeout: 300_000 }),
  // Submit can take up to 5 min for a full mock exam with many LLM calls
  submit: (sessionId, answers) => api.post(`/test/submit/${sessionId}`, answers, { timeout: 300_000 }),
  uploadAnswer: (questionId, file) => {
    const form = new FormData();
    form.append("file", file);
    return api.post(`/test/upload-answer/${questionId}`, form);
  },
};

export const upload = {
  uploadDocument: (formData) =>
    api.post("/upload/document", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60_000,
    }),
  documents: () => api.get("/upload/documents"),
  subjects: () => api.get("/upload/subjects"),
  deleteDocument: (id) => api.delete(`/upload/document/${id}`),
  generateTest: (subjectName, mode) =>
    api.post(`/upload/test/${encodeURIComponent(subjectName)}?mode=${mode}`, {}),
};
