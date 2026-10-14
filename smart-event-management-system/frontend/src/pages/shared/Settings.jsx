import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { FiLock, FiMoon, FiSun, FiLogOut, FiTrash2, FiAlertTriangle, FiEye, FiEyeOff, FiBell } from "react-icons/fi";
import { useTheme } from "../../context/ThemeContext.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { userService } from "../../api/services.js";
import Modal from "../../components/ui/Modal.jsx";

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const { user, logout, deleteAccount, updateUser } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ current_password: "", new_password: "", confirm_new_password: "" });
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [notifPrefs, setNotifPrefs] = useState({
    in_app: user?.notification_preferences?.in_app ?? true,
    email: user?.notification_preferences?.email ?? true,
  });

  useEffect(() => {
    if (user?.notification_preferences) {
      setNotifPrefs({
        in_app: user.notification_preferences.in_app ?? true,
        email: user.notification_preferences.email ?? true,
      });
    }
  }, [user]);

  const handleToggleNotif = async (key, val) => {
    const updated = { ...notifPrefs, [key]: val };
    setNotifPrefs(updated);
    try {
      const res = await userService.updateNotificationPreferences(updated);
      if (updateUser && res.data) {
        updateUser(res.data);
      }
      toast.success(`${key === "in_app" ? "In-app" : "Email"} notification preference saved.`);
    } catch (err) {
      toast.error("Failed to update notification preferences.");
      setNotifPrefs(notifPrefs);
    }
  };

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.current_password) return toast.error("Current password is required");
    if (!form.new_password) return toast.error("New password is required");
    if (form.new_password.length < 8) return toast.error("Password must be at least 8 characters.");
    if (form.new_password !== form.confirm_new_password) return toast.error("Passwords do not match.");
    setSaving(true);
    try {
      await userService.changePassword(form);
      toast.success("Password updated successfully");
      setForm({ current_password: "", new_password: "", confirm_new_password: "" });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not update password");
    } finally {
      setSaving(false);
    }
  };

  const handleSignOut = () => {
    logout();
    toast.success("Signed out successfully");
    navigate("/login", { replace: true });
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await deleteAccount();
      toast.success("Your account has been deactivated and deleted.");
      setDeleteModalOpen(false);
      navigate("/login", { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not delete account. Please try again.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Settings</h1>
      <p className="page-subtitle">Manage your account security, appearance preferences, and session.</p>

      <div className="grid-cards-2" style={{ alignItems: "start" }}>
        {/* Security / Password */}
        <div className="glass-card" style={{ padding: 28 }}>
          <h3 style={{ fontSize: 16, marginBottom: 18, display: "flex", alignItems: "center", gap: 8 }}>
            <FiLock /> Change Password
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Current Password</label>
              <div style={{ position: "relative" }}>
                <input
                  className="form-input"
                  type={showCurrent ? "text" : "password"}
                  value={form.current_password}
                  onChange={update("current_password")}
                  placeholder="••••••••"
                  style={{ paddingRight: "40px" }}
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  tabIndex={-1}
                  style={{
                    position: "absolute",
                    right: 12,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  {showCurrent ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                </button>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">New Password</label>
              <div style={{ position: "relative" }}>
                <input
                  className="form-input"
                  type={showNew ? "text" : "password"}
                  value={form.new_password}
                  onChange={update("new_password")}
                  placeholder="••••••••"
                  style={{ paddingRight: "40px" }}
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  tabIndex={-1}
                  style={{
                    position: "absolute",
                    right: 12,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  {showNew ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                </button>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Confirm New Password</label>
              <div style={{ position: "relative" }}>
                <input
                  className="form-input"
                  type={showConfirm ? "text" : "password"}
                  value={form.confirm_new_password}
                  onChange={update("confirm_new_password")}
                  placeholder="••••••••"
                  style={{ paddingRight: "40px" }}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  tabIndex={-1}
                  style={{
                    position: "absolute",
                    right: 12,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  {showConfirm ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                </button>
              </div>
            </div>
            <button className="btn btn-primary" disabled={saving}>
              {saving ? "Updating..." : "Update Password"}
            </button>
          </form>
        </div>

        {/* Appearance & Account Actions */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="glass-card" style={{ padding: 28 }}>
            <h3 style={{ fontSize: 16, marginBottom: 18 }}>Appearance</h3>
            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", marginBottom: 18 }}>
              Choose how EventSphere looks on this device. Your choice is saved automatically.
            </p>
            <div style={{ display: "flex", gap: 14 }}>
              <button
                type="button"
                onClick={() => setTheme("light")}
                className="btn"
                style={{
                  flex: 1,
                  flexDirection: "column",
                  height: 90,
                  gap: 8,
                  background: theme === "light" ? "var(--gradient-primary)" : "var(--bg-base)",
                  color: theme === "light" ? "#fff" : "var(--text-primary)",
                  border: "1.5px solid var(--border-color)",
                }}
              >
                <FiSun size={20} /> Light Mode
              </button>
              <button
                type="button"
                onClick={() => setTheme("dark")}
                className="btn"
                style={{
                  flex: 1,
                  flexDirection: "column",
                  height: 90,
                  gap: 8,
                  background: theme === "dark" ? "var(--gradient-primary)" : "var(--bg-base)",
                  color: theme === "dark" ? "#fff" : "var(--text-primary)",
                  border: "1.5px solid var(--border-color)",
                }}
              >
                <FiMoon size={20} /> Dark Mode
              </button>
            </div>
          </div>

          {/* Notification Preferences */}
          <div className="glass-card" style={{ padding: 28 }}>
            <h3 style={{ fontSize: 16, marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
              <FiBell /> Notification Preferences
            </h3>
            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", marginBottom: 18 }}>
              Choose your notification preferences for event updates, approval decisions, and certificates.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* In-App Notifications */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 16px",
                  borderRadius: 12,
                  background: "var(--bg-base)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 2 }}>In-App Notifications</div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    Receive real-time alerts in your notification bell
                  </div>
                </div>
                <label style={{ cursor: "pointer", display: "inline-flex", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={notifPrefs.in_app}
                    onChange={(e) => handleToggleNotif("in_app", e.target.checked)}
                    style={{ width: 18, height: 18, cursor: "pointer", accentColor: "var(--primary-color, #8b5cf6)" }}
                  />
                </label>
              </div>

              {/* Email Notifications */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 16px",
                  borderRadius: 12,
                  background: "var(--bg-base)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 2 }}>Email Notifications</div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    Receive approval, rejection, and certificate emails
                  </div>
                </div>
                <label style={{ cursor: "pointer", display: "inline-flex", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={notifPrefs.email}
                    onChange={(e) => handleToggleNotif("email", e.target.checked)}
                    style={{ width: 18, height: 18, cursor: "pointer", accentColor: "var(--primary-color, #8b5cf6)" }}
                  />
                </label>
              </div>

              {/* Security Email Notice */}
              <div
                style={{
                  padding: "10px 12px",
                  borderRadius: 10,
                  background: "rgba(139, 92, 246, 0.08)",
                  border: "1px solid rgba(139, 92, 246, 0.2)",
                  fontSize: 11.5,
                  color: "var(--text-secondary)",
                  lineHeight: 1.45,
                }}
              >
                <strong style={{ color: "var(--text-primary)", display: "block", marginBottom: 2 }}>
                  Essential Security Email Note:
                </strong>
                Disabling email notifications only mutes event and certificate alerts. Essential security emails (OTP verification & password reset) will always be delivered.
              </div>
            </div>
          </div>

          {/* Account Management: Sign Out & Delete Account */}
          <div
            className="glass-card"
            style={{
              padding: 28,
              border: "1.5px solid rgba(239, 68, 68, 0.25)",
              background: "var(--bg-elevated)",
            }}
          >
            <h3 style={{ fontSize: 16, marginBottom: 8, color: "var(--danger)", display: "flex", alignItems: "center", gap: 8 }}>
              <FiAlertTriangle /> Account Actions
            </h3>
            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", marginBottom: 20 }}>
              End your active session or permanently remove your account from EventSphere.
            </p>

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={handleSignOut}
                className="btn btn-outline"
                style={{ flex: 1, minWidth: 140, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
              >
                <FiLogOut /> Sign Out
              </button>

              <button
                type="button"
                onClick={() => setDeleteModalOpen(true)}
                className="btn"
                style={{
                  flex: 1,
                  minWidth: 140,
                  background: "rgba(239, 68, 68, 0.15)",
                  color: "var(--danger)",
                  border: "1px solid rgba(239, 68, 68, 0.35)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                }}
              >
                <FiTrash2 /> Delete Account
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Account Confirmation Dialog */}
      <Modal
        open={deleteModalOpen}
        onClose={() => !deleting && setDeleteModalOpen(false)}
        title="Delete Account?"
      >
        <div style={{ padding: "8px 0" }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: "50%",
              background: "rgba(239, 68, 68, 0.15)",
              color: "var(--danger)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
            }}
          >
            <FiTrash2 size={26} />
          </div>
          <p style={{ fontSize: 14, color: "var(--text-primary)", textAlign: "center", lineHeight: 1.6, marginBottom: 8, fontWeight: 600 }}>
            Are you sure you want to delete your account?
          </p>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", textAlign: "center", lineHeight: 1.5, marginBottom: 24 }}>
            This action will permanently remove/deactivate your account. You will be signed out immediately and will not be able to log back in.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => setDeleteModalOpen(false)}
              disabled={deleting}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn"
              onClick={handleDeleteAccount}
              disabled={deleting}
              style={{
                background: "var(--danger)",
                color: "#fff",
                border: "none",
                fontWeight: 600,
              }}
            >
              {deleting ? "Deleting..." : "Delete Account"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
