import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { FiMail, FiLock, FiEye, FiEyeOff, FiCalendar, FiCheckCircle, FiArrowLeft } from "react-icons/fi";
import ThemeToggle from "../../components/common/ThemeToggle.jsx";
import PageTransition from "../../components/common/PageTransition.jsx";
import OTPInput from "../../components/common/OTPInput.jsx";
import TestUsersModal from "../../components/auth/TestUsersModal.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { authService } from "../../api/services.js";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [role, setRole] = useState("student");

  // Test users modal state
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);

  // Password state
  const [form, setForm] = useState({ email: "", password: "", remember_me: false });
  const [showPassword, setShowPassword] = useState(false);

  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const update = (field) => (e) =>
    setForm((f) => ({ ...f, [field]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const getDashboardDestination = (user) => {
    const userRole = (user?.role || "").toLowerCase();
    const status = (user?.approval_status || (userRole === "admin" ? "APPROVED" : "PENDING")).toUpperCase();
    if (userRole !== "admin" && status !== "APPROVED" && status !== "ACTIVE") {
      return "/awaiting-approval";
    }
    if (userRole === "admin") return "/admin/dashboard";
    if (userRole === "faculty") return "/faculty/dashboard";
    if (userRole === "volunteer") return "/volunteer/dashboard";
    return "/student/dashboard";
  };

  const getAuthErrorMessage = (err) => {
    if (!err) return "Login failed. Please check your credentials.";
    if (err.code === "ERR_NETWORK" || err.message === "Network Error") {
      return "Authentication server is unavailable. Please make sure the EventSphere backend is running.";
    }
    const status = err.response?.status;
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) return detail[0].message || detail[0];
    if (status === 401) return "Invalid email or password.";
    if (status === 403) return "Your account does not have permission for this role, or email is unverified.";
    if (status === 404) return "Account not found. Please register first.";
    if (status >= 500) return "Authentication service encountered an error. Please try again.";
    if (err.message) return err.message;
    return "Login failed. Please check your credentials.";
  };

  const handleUseAccount = (account) => {
    setRole(account.role);
    setForm((f) => ({ ...f, email: account.email, password: account.password }));
    setIsTestModalOpen(false);
    toast.success(`${account.label} demo account loaded`);
  };

  const handleLoginNow = async (account) => {
    setRole(account.role);
    setForm((f) => ({ ...f, email: account.email, password: account.password }));
    setSubmitting(true);
    try {
      const user = await login({
        email: account.email,
        password: account.password,
        role: account.role,
        remember_me: form.remember_me,
      });
      setIsTestModalOpen(false);
      toast.success(`Welcome back, ${user?.name ? user.name.split(" ")[0] : "User"}!`);
      const dest = getDashboardDestination(user);
      navigate(dest, { replace: true });
    } catch (err) {
      if (!err.response) {
        toast.error(err.message || "Login failed. Please try again.");
        return;
      }
      const msg = getAuthErrorMessage(err);
      toast.error(msg);
      if (err.response?.data?.detail === "Please verify your email first") {
        navigate("/verify-email", { state: { email: account.email } });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const validatePasswordForm = () => {
    const e = {};
    if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = "Enter a valid email address";
    if (!form.password) e.password = "Password is required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    if (!validatePasswordForm()) return;
    setSubmitting(true);
    try {
      const user = await login({ ...form, role });
      toast.success(`Welcome back, ${user?.name ? user.name.split(" ")[0] : "User"}!`);
      const dest = getDashboardDestination(user);
      navigate(dest, { replace: true });
    } catch (err) {
      const msg = getAuthErrorMessage(err);
      toast.error(msg);
      if (err.response?.data?.detail === "Please verify your email first") {
        navigate("/verify-email", { state: { email: form.email } });
      }
    } finally {
      setSubmitting(false);
    }
  };


  const inputIconStyle = {
    position: "absolute",
    left: 12,
    top: "50%",
    transform: "translateY(-50%)",
    color: "var(--text-muted)",
    pointerEvents: "none",
    fontSize: 16,
  };

  return (
    <PageTransition>
      <div
        className="auth-shell"
        style={{
          position: "relative",
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          overflow: "hidden",
        }}
      >
        {/* Ambient Blurred Background Lights */}
        <div
          aria-hidden
          style={{
            position: "absolute",
            top: -100,
            left: "20%",
            width: 450,
            height: 450,
            borderRadius: "50%",
            background: "rgba(139, 92, 246, 0.16)",
            filter: "blur(80px)",
            pointerEvents: "none",
          }}
        />
        <div
          aria-hidden
          style={{
            position: "absolute",
            bottom: -80,
            right: "20%",
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: "rgba(99, 102, 241, 0.14)",
            filter: "blur(90px)",
            pointerEvents: "none",
          }}
        />

        {/* Floating Theme Switcher */}
        <div style={{ position: "absolute", top: 24, right: 24, zIndex: 10 }}>
          <ThemeToggle />
        </div>

        {/* Login Island Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="glass-card auth-card float-card"
          style={{
            width: "100%",
            maxWidth: 460,
            padding: "36px 32px",
            borderRadius: "26px",
            background: "var(--bg-elevated)",
            border: "1.5px solid rgba(139, 92, 246, 0.3)",
            boxShadow: "0 24px 60px rgba(0, 0, 0, 0.4), 0 0 35px rgba(139, 92, 246, 0.18)",
            position: "relative",
            zIndex: 2,
          }}
        >
          {/* Back button */}
        <button
          type="button"
          onClick={() => {
            if (window.history.length > 1) navigate(-1);
            else navigate("/");
          }}
          aria-label="Go back"
          title="Go back"
          style={{
            position: "absolute",
            top: 18,
            left: 18,
            width: 38,
            height: 38,
            borderRadius: 11,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "var(--bg-glass)",
            border: "1px solid var(--border-color)",
            color: "var(--text-secondary)",
            cursor: "pointer",
            zIndex: 3,
          }}
        >
          <FiArrowLeft size={17} />
        </button>

        {/* Header */}
          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <Link
              to="/"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                fontWeight: 800,
                fontSize: 18,
                marginBottom: 16,
              }}
            >
              <motion.span
                whileHover={{ scale: 1.08, rotate: 6 }}
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 12,
                  background: "var(--gradient-primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  boxShadow: "0 6px 16px rgba(139, 92, 246, 0.4)",
                }}
              >
                <FiCalendar size={18} />
              </motion.span>
              <span>
                Event<span className="text-gradient">Sphere</span>
              </span>
            </Link>
            <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Welcome back</h1>
            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", margin: 0 }}>
              Sign in to continue to your dashboard
            </p>
          </div>

          {/* Role Pill Switcher */}
          <div
            style={{
              display: "flex",
              background: "var(--bg-base)",
              borderRadius: 999,
              padding: 4,
              marginBottom: 16,
              border: "1px solid var(--border-color)",
            }}
          >
            {[
              { id: "student", label: "Student" },
              { id: "faculty", label: "Faculty" },
              { id: "volunteer", label: "Volunteer" },
              { id: "admin", label: "Admin" },
            ].map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setRole(r.id)}
                className="btn btn-sm"
                style={{
                  flex: 1,
                  background: role === r.id ? "var(--gradient-primary)" : "transparent",
                  color: role === r.id ? "#fff" : "var(--text-secondary)",
                  borderRadius: 999,
                  transition: "all 0.2s ease",
                  fontWeight: role === r.id ? 600 : 500,
                  fontSize: 12,
                  padding: "6px 4px",
                }}
              >
                {r.label}
              </button>
            ))}
          </div>

          {/* Firebase Authentication */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: "9px 12px",
              marginBottom: 18,
              borderRadius: 10,
              background: "rgba(139, 92, 246, 0.08)",
              border: "1px solid rgba(139, 92, 246, 0.22)",
              color: "var(--text-secondary)",
              fontSize: 12.5,
            }}
          >
            <FiCheckCircle size={14} style={{ color: "#8b5cf6" }} />
            Email and password are secured by Firebase Authentication
          </div>

          {/* METHOD 1: PASSWORD LOGIN */}
          <form onSubmit={handlePasswordSubmit}>
              <div className="form-group">
                <label className="form-label">Email Address</label>
                <div style={{ position: "relative" }}>
                  <FiMail style={inputIconStyle} />
                  <input
                    className="form-input"
                    style={{ paddingLeft: 40 }}
                    type="email"
                    value={form.email}
                    onChange={update("email")}
                    placeholder="you@college.edu"
                    required
                  />
                </div>
                {errors.email && <span className="form-error">{errors.email}</span>}
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <div style={{ position: "relative" }}>
                  <FiLock style={inputIconStyle} />
                  <input
                    className="form-input"
                    style={{ paddingLeft: 40, paddingRight: 40 }}
                    type={showPassword ? "text" : "password"}
                    value={form.password}
                    onChange={update("password")}
                    placeholder="••••••••"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    style={{
                      ...inputIconStyle,
                      left: "auto",
                      right: 12,
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    {showPassword ? <FiEyeOff /> : <FiEye />}
                  </button>
                </div>
                {errors.password && <span className="form-error">{errors.password}</span>}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-secondary)", cursor: "pointer" }}>
                  <input type="checkbox" checked={form.remember_me} onChange={update("remember_me")} />
                  Remember me
                </label>
                <Link to="/forgot-password" style={{ fontSize: 13, color: "#8b5cf6", fontWeight: 600 }}>
                  Forgot password?
                </Link>
              </div>

              <button className="btn btn-primary" style={{ width: "100%" }} disabled={submitting}>
                {submitting ? "Logging in..." : "Login with Password"}
              </button>
          </form>

          {/* Footer link to Register */}
          <div style={{ textAlign: "center", marginTop: 22, fontSize: 13.5, color: "var(--text-secondary)" }}>
            Don't have an account?{" "}
            <Link to="/register" style={{ color: "#8b5cf6", fontWeight: 600 }}>
              Register here
            </Link>
          </div>

          {/* Secondary Test Users Section */}
          <div
            style={{
              marginTop: 20,
              paddingTop: 18,
              borderTop: "1px dashed var(--border-color)",
              textAlign: "center",
            }}
          >
            <button
              type="button"
              onClick={() => setIsTestModalOpen(true)}
              style={{
                background: "var(--bg-glass)",
                border: "1px solid rgba(139, 92, 246, 0.3)",
                color: "var(--text-primary)",
                borderRadius: 12,
                padding: "8px 18px",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "#8b5cf6";
                e.currentTarget.style.background = "rgba(139, 92, 246, 0.1)";
                e.currentTarget.style.transform = "translateY(-1px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(139, 92, 246, 0.3)";
                e.currentTarget.style.background = "var(--bg-glass)";
                e.currentTarget.style.transform = "none";
              }}
            >
              <span>🧪</span>
              <span>Test Users</span>
            </button>
            <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--text-muted)" }}>
              Quick access to demo accounts
            </p>
          </div>
        </motion.div>

        {/* Interactive Glassmorphism Test Users Modal */}
        <TestUsersModal
          isOpen={isTestModalOpen}
          onClose={() => setIsTestModalOpen(false)}
          onUseAccount={handleUseAccount}
          onLoginNow={handleLoginNow}
          isLoggingIn={submitting}
        />
      </div>
    </PageTransition>
  );
}
