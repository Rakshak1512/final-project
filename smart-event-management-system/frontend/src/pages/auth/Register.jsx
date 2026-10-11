import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { FiCalendar, FiUpload } from "react-icons/fi";
import ThemeToggle from "../../components/common/ThemeToggle.jsx";
import PageTransition from "../../components/common/PageTransition.jsx";
import { useAuth } from "../../context/AuthContext.jsx";

const departments = ["Computer Science", "Electronics", "Mechanical", "Civil", "Electrical", "Information Technology", "MBA", "Other"];
const semesters = ["1", "2", "3", "4", "5", "6", "7", "8"];

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    role: "student",
    name: "",
    registration_number: "",
    admin_id: "",
    department: "",
    semester: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [pictureFile, setPictureFile] = useState(null);
  const [picturePreview, setPicturePreview] = useState(null);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handlePicture = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPictureFile(file);
    setPicturePreview(URL.createObjectURL(file));
  };

  const validate = () => {
    const e = {};
    if (form.name.trim().length < 2) e.name = "Enter your full name";
    if (form.role === "student") {
      if (!form.registration_number.trim()) e.registration_number = "Registration number is required";
      if (!form.department) e.department = "Select your department";
      if (!form.semester) e.semester = "Select your semester";
    } else if (form.role === "faculty" || form.role === "volunteer") {
      if (!form.department) e.department = "Select your department";
    } else if (form.role === "admin") {
      if (!form.admin_id.trim()) e.admin_id = "Admin ID is required";
    }
    if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = "Enter a valid email address";
    if (form.password.length < 8) e.password = "Password must be at least 8 characters";
    if (form.confirm_password !== form.password) e.confirm_password = "Passwords do not match";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload = {
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        confirm_password: form.confirm_password,
        role: form.role,
        registration_number:
          form.role === "student"
            ? form.registration_number.trim()
            : form.role === "admin"
            ? form.admin_id.trim()
            : undefined,
        admin_id: form.role === "admin" ? form.admin_id.trim() : undefined,
        department: form.role === "admin" ? undefined : form.department || undefined,
        semester: form.role === "student" ? form.semester || undefined : undefined,
      };

      await register(payload);
      toast.success("Verification OTP sent to your email!");
      navigate("/verify-email", { state: { email: form.email.trim().toLowerCase(), role: form.role, name: form.name.trim() } });
    } catch (err) {
      const detail = err.response?.data?.detail;
      let msg = "Registration failed. Please check your details.";
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail
          .map((d) => {
            if (typeof d === "string") return d;
            const fieldName = (d.field || (Array.isArray(d.loc) ? d.loc.join(".") : "") || "")
              .replace(/^(body\.|query\.)/, "")
              .replace(/_/g, " ");
            const errMsg = d.message || d.msg || "Invalid value";
            return fieldName ? `${fieldName}: ${errMsg}` : errMsg;
          })
          .join("; ");
      } else if (detail && typeof detail === "object") {
        msg = detail.message || detail.msg || JSON.stringify(detail);
      } else if (err.response?.data?.message) {
        msg = err.response.data.message;
      }
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
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
            top: -120,
            left: -100,
            width: 480,
            height: 480,
            borderRadius: "50%",
            background: "var(--gradient-primary)",
            opacity: 0.16,
            filter: "blur(90px)",
            pointerEvents: "none",
          }}
        />
        <div
          aria-hidden
          style={{
            position: "absolute",
            bottom: -100,
            right: -80,
            width: 450,
            height: 450,
            borderRadius: "50%",
            background: "rgba(14, 165, 233, 0.14)",
            filter: "blur(80px)",
            pointerEvents: "none",
          }}
        />

        <div style={{ position: "absolute", top: 24, right: 24, zIndex: 10 }}>
          <ThemeToggle />
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="glass-card auth-card float-card"
          style={{
            width: "100%",
            maxWidth: 540,
            padding: "36px 32px",
            borderRadius: "26px",
            background: "var(--bg-elevated)",
            border: "1.5px solid rgba(139, 92, 246, 0.3)",
            boxShadow: "0 24px 60px rgba(0, 0, 0, 0.4), 0 0 35px rgba(139, 92, 246, 0.18)",
            position: "relative",
            zIndex: 2,
          }}
        >
          <div style={{ textAlign: "center", marginBottom: 24 }}>
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
            <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>Create your account</h1>
            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", margin: 0 }}>
              Join your campus event ecosystem in under a minute
            </p>
          </div>

          {/* 4-Role Selector */}
          <div
            style={{
              display: "flex",
              background: "var(--bg-base)",
              borderRadius: 999,
              padding: 4,
              marginBottom: 22,
              border: "1px solid var(--border-color)",
              gap: 2,
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
                onClick={() => setForm((f) => ({ ...f, role: r.id }))}
                className="btn btn-sm"
                style={{
                  flex: 1,
                  background: form.role === r.id ? "var(--gradient-primary)" : "transparent",
                  color: form.role === r.id ? "#fff" : "var(--text-secondary)",
                  borderRadius: 999,
                  transition: "all 0.2s ease",
                  fontWeight: form.role === r.id ? 600 : 500,
                  fontSize: 12,
                  padding: "6px 2px",
                  whiteSpace: "nowrap",
                }}
              >
                {r.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                className="form-input"
                value={form.name}
                onChange={update("name")}
                placeholder="Jane Doe"
                required
              />
              {errors.name && <span className="form-error">{errors.name}</span>}
            </div>

            {/* Admin Specific Field: Admin ID */}
            {form.role === "admin" && (
              <div className="form-group">
                <label className="form-label">Admin ID</label>
                <input
                  className="form-input"
                  value={form.admin_id}
                  onChange={update("admin_id")}
                  placeholder="ADM-1001"
                  required
                />
                {errors.admin_id && <span className="form-error">{errors.admin_id}</span>}
              </div>
            )}

            {/* Student Specific Fields */}
            {form.role === "student" && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div className="form-group">
                    <label className="form-label">Registration Number</label>
                    <input
                      className="form-input"
                      value={form.registration_number}
                      onChange={update("registration_number")}
                      placeholder="21CS1023"
                      required
                    />
                    {errors.registration_number && <span className="form-error">{errors.registration_number}</span>}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Department</label>
                    <select className="form-select" value={form.department} onChange={update("department")} required>
                      <option value="">Select department</option>
                      {departments.map((d) => (
                        <option key={d} value={d}>
                          {d}
                        </option>
                      ))}
                    </select>
                    {errors.department && <span className="form-error">{errors.department}</span>}
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Semester</label>
                  <select className="form-select" value={form.semester} onChange={update("semester")} required>
                    <option value="">Select semester</option>
                    {semesters.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  {errors.semester && <span className="form-error">{errors.semester}</span>}
                </div>
              </>
            )}

            {/* Faculty and Volunteer Specific Field: Department */}
            {(form.role === "faculty" || form.role === "volunteer") && (
              <div className="form-group">
                <label className="form-label">Department</label>
                <select className="form-select" value={form.department} onChange={update("department")} required>
                  <option value="">Select department</option>
                  {departments.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
                {errors.department && <span className="form-error">{errors.department}</span>}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Email Address</label>
              <input
                className="form-input"
                type="email"
                value={form.email}
                onChange={update("email")}
                placeholder="you@college.edu"
                required
              />
              {errors.email && <span className="form-error">{errors.email}</span>}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  className="form-input"
                  type="password"
                  value={form.password}
                  onChange={update("password")}
                  placeholder="••••••••"
                  required
                />
                {errors.password && <span className="form-error">{errors.password}</span>}
              </div>
              <div className="form-group">
                <label className="form-label">Confirm Password</label>
                <input
                  className="form-input"
                  type="password"
                  value={form.confirm_password}
                  onChange={update("confirm_password")}
                  placeholder="••••••••"
                  required
                />
                {errors.confirm_password && <span className="form-error">{errors.confirm_password}</span>}
              </div>
            </div>

            <button className="btn btn-primary" style={{ width: "100%", marginTop: 6 }} disabled={submitting}>
              {submitting ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <p style={{ textAlign: "center", fontSize: 13.5, color: "var(--text-secondary)", marginTop: 22 }}>
            Already have an account?{" "}
            <Link to="/login" style={{ color: "#8b5cf6", fontWeight: 600 }}>
              Login
            </Link>
          </p>
        </motion.div>
      </div>
    </PageTransition>
  );
}
