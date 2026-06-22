import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import TestRequest from "./pages/TestRequest";
import TestAttempt from "./pages/TestAttempt";
import Results from "./pages/Results";

function PrivateRoute({ children }) {
  const { student, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading...</div>;
  return student ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const { student, loading } = useAuth();
  if (loading) return null;
  return student ? <Navigate to="/dashboard" replace /> : children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
          <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/test" element={<PrivateRoute><TestRequest /></PrivateRoute>} />
          <Route path="/test/attempt" element={<PrivateRoute><TestAttempt /></PrivateRoute>} />
          <Route path="/test/results" element={<PrivateRoute><Results /></PrivateRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
