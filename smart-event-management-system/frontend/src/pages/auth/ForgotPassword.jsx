import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import {
  FiArrowLeft,
  FiCalendar,
  FiCheckCircle,
  FiLock,
  FiMail,
  FiEye,
  FiEyeOff,
  FiShield,
  FiKey,
  FiAlertCircle,
} from "react-icons/fi";
import ThemeToggle from "../../components/common/ThemeToggle.jsx";
import PageTransition from "../../components/common/PageTransition.jsx";
import OTPInput from "../../components/common/OTPInput.jsx";
import { authService } from "../../api/services.js";

function maskEmail(email) {
  if (!email || !email.includes("@")) return "***";
  const [local, domain] = email.split("@");
  if (local.length <= 2) return `${local[0]}*@${domain}`;
  return `${local[0]}${"*".repeat(Math.max(1, local.length - 2))}${local[local.length - 1]}@${domain}`;
}

export default function ForgotPassword() {
  const navigate = useNavigate();

  // Multi-step flow: "request" -> "verify" -> "reset" -> "done"
  const [step, setStep] = useState("request");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Loading and error states
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [otpError, setOtpError] = useState(false);

  // Step 1: Request Password Reset OTP
  const handleRequestOtp = async (e) => {
    e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    if (!/^\S+@\S+\.\S+$/.test(cleanEmail)) {
      toast.error("Please enter a valid email address.");
      return;
    }

    setSubmitting(true);
    setErrorMessage("");
    try {
      await authService.forgotPassword({ email: cleanEmail });
      toast.success("Password reset OTP sent! Please check your email.");
      setStep("verify");
    } catch (err) {
      const detail = err.response?.data?.detail;
      let msg = "Could not send password reset OTP. Please try again.";
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail[0].message || detail[0];
      }
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Resend OTP handler for Step 2
  const handleResendOtp = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) return;

    setResending(true);
    setErrorMessage("");
    setOtpError(false);
    try {
      await authService.forgotPassword({ email: cleanEmail });
      toast.success("A new 6-digit OTP has been sent to your email!");
      setOtp("");
    } catch (err) {
      const detail = err.response?.data?.detail;
      let msg = "Could not resend OTP. Please wait before retrying.";
      if (typeof detail === "string") {
        msg = detail;
      }
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setResending(false);
    }
  };

  // Step 2: Verify Submitted OTP
  const handleVerifyOtp = async (codeToVerify) => {
    const code = (codeToVerify || otp).trim();
    if (code.length !== 6) {
      setErrorMessage("Please enter all 6 digits of the OTP code.");
      setOtpError(true);
      return;
    }

    setSubmitting(true);
    setErrorMessage("");
    setOtpError(false);
    try {
      await authService.verifyResetOtp({
        email: email.trim().toLowerCase(),
        otp_code: code,
      });
      toast.success("OTP verified successfully!");
      setStep("reset");
    } catch (err) {
      const detail = err.response?.data?.detail;
      let msg = "Invalid OTP. Please check and try again.";
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail[0].message || detail[0];
      }
      setErrorMessage(msg);
      setOtpError(true);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Step 3: Set New Password
  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      toast.error("Password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    setErrorMessage("");
    try {
      await authService.resetPassword({
        email: email.trim().toLowerCase(),
        otp_code: otp.trim(),
        new_password: newPassword,
        confirm_new_password: confirmPassword,
      });
      toast.success("Password reset successfully!");
      setStep("done");
    } catch (err) {
      const detail = err.response?.data?.detail;
      let msg = "Unable to reset password. Please try again.";
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail[0].message || detail[0];
      }
      setErrorMessage(msg);
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
          padding: "24px 16px",
          background: "var(--bg-base, #0b0f19)",
          overflow: "hidden",
        }}
      >
        {/* Ambient Blurred Background Lights */}
        <div
          aria-hidden
          style={{
            position: "absolute",
            top: -120,
            left: "20%",
            width: 480,
            height: 480,
            borderRadius: "50%",
            background: "rgba(139, 92, 246, 0.16)",
            filter: "blur(90px)",
            pointerEvents: "none",
          }}
        />
        <div
          aria-hidden
          style={{
            position: "absolute",
            bottom: -100,
            right: "20%",
            width: 450,
            height: 450,
            borderRadius: "50%",
            background: "rgba(99, 102, 241, 0.14)",
            filter: "blur(80px)",
            pointerEvents: "none",
          }}
        />

        {/* Top Navigation */}
        <div style={{ position: "absolute", top: 24, left: 24, zIndex: 10 }}>
          <button
            type="button"
            onClick={() => {
              if (step === "verify") setStep("request");
              else if (step === "reset") setStep("verify");
              else navigate("/login");
            }}
            aria-label="Go back"
            title="Go back"
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "var(--bg-glass, rgba(255, 255, 255, 0.05))",
              border: "1px solid var(--border-color, rgba(255, 255, 255, 0.1))",
              color: "var(--text-secondary, #94a3b8)",
              cursor: "pointer",
            }}
          >
            <FiArrowLeft size={18} />
          </button>
        </div>

        <div style={{ position: "absolute", top: 24, right: 24, zIndex: 10 }}>
          <ThemeToggle />
        </div>

        {/* Main Card */}
        <motion.div
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="glass-card auth-card"
          style={{
            width: "100%",
            maxWidth: 500,
            padding: "36px 32px",
            borderRadius: 24,
            background: "var(--bg-elevated)",
            border: "1.5px solid rgba(139, 92, 246, 0.3)",
            boxShadow: "0 24px 60px rgba(0, 0, 0, 0.45), 0 0 35px rgba(139, 92, 246, 0.15)",
            position: "relative",
            zIndex: 2,
          }}
        >
          {/* Brand Header */}
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
              <span
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 12,
                  background: "var(--gradient-primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                }}
              >
                <FiCalendar size={18} />
              </span>
              Event<span className="text-gradient">Sphere</span>
            </Link>

            {/* Icon Header */}
            <div
              style={{
                width: 58,
                height: 58,
                borderRadius: "50%",
                background: "var(--gradient-soft, rgba(139, 92, 246, 0.12))",
                color: "#8b5cf6",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 14px",
                border: "1px solid rgba(139, 92, 246, 0.25)",
              }}
            >
              {step === "request" && <FiLock size={24} />}
              {step === "verify" && <FiShield size={24} />}
              {step === "reset" && <FiKey size={24} />}
              {step === "done" && <FiCheckCircle size={26} color="#10b981" />}
            </div>

            <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6, color: "var(--text-primary)" }}>
              {step === "request" && "Forgot Password"}
              {step === "verify" && "Verify Reset OTP"}
              {step === "reset" && "Set New Password"}
              {step === "done" && "Password Reset Successful"}
            </h1>

            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", margin: 0, lineHeight: 1.6 }}>
              {step === "request" &&
                "Enter your registered email address and we will dispatch a secure 6-digit verification OTP."}
              {step === "verify" && (
                <>
                  Enter the 6-digit verification code sent to{" "}
                  <strong style={{ color: "var(--text-primary)" }}>{maskEmail(email)}</strong>. It expires in 5 minutes.
                </>
              )}
              {step === "reset" && "Create a secure new password for your EventSphere account."}
              {step === "done" && "Your password has been updated. You can now login with your new credentials."}
            </p>
          </div>

          {/* Error Notice */}
          <AnimatePresence>
            {errorMessage && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                style={{
                  background: "rgba(239, 68, 68, 0.12)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: 12,
                  padding: "12px 14px",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  color: "#ef4444",
                  fontSize: 13.5,
                  marginBottom: 18,
                }}
              >
                <FiAlertCircle size={18} style={{ flexShrink: 0 }} />
                <span>{errorMessage}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* STEP 1: Enter email and send OTP */}
          {step === "request" && (
            <form onSubmit={handleRequestOtp}>
              <div className="form-group" style={{ marginBottom: 20 }}>
                <label className="form-label" style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, display: "block" }}>
                  Registered Email Address
                </label>
                <div style={{ position: "relative" }}>
                  <FiMail
                    style={{
                      position: "absolute",
                      left: 14,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                      pointerEvents: "none",
                      fontSize: 16,
                    }}
                  />
                  <input
                    className="form-input"
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (errorMessage) setErrorMessage("");
                    }}
                    placeholder="you@college.edu"
                    required
                    autoFocus
                    style={{
                      width: "100%",
                      padding: "12px 16px 12px 42px",
                      borderRadius: 12,
                      background: "var(--input-bg, rgba(255, 255, 255, 0.05))",
                      border: "1px solid var(--border-color)",
                      color: "var(--text-primary)",
                      fontSize: 14.5,
                    }}
                  />
                </div>
              </div>

              {/* Requirement: Exactly 'Send Password Reset OTP' */}
              <button
                type="submit"
                className="btn btn-primary"
                style={{
                  width: "100%",
                  padding: "13px",
                  borderRadius: 12,
                  fontSize: 14.5,
                  fontWeight: 600,
                  cursor: submitting ? "not-allowed" : "pointer",
                }}
                disabled={submitting}
              >
                {submitting ? "Sending OTP..." : "Send Password Reset OTP"}
              </button>
            </form>
          )}

          {/* STEP 2: 6-Box OTP Verification Screen */}
          {step === "verify" && (
            <div>
              <OTPInput
                value={otp}
                onChange={(val) => {
                  setOtp(val);
                  if (errorMessage) setErrorMessage("");
                  setOtpError(false);
                }}
                onComplete={handleVerifyOtp}
                onResend={handleResendOtp}
                resending={resending}
                disabled={submitting}
                error={otpError}
                errorMessage={errorMessage}
                expiryMinutes={5}
                initialCooldown={60}
              />

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => handleVerifyOtp()}
                disabled={submitting || otp.length !== 6}
                style={{
                  width: "100%",
                  padding: "13px",
                  borderRadius: 12,
                  fontSize: 14.5,
                  fontWeight: 600,
                  marginTop: 18,
                  cursor: submitting || otp.length !== 6 ? "not-allowed" : "pointer",
                }}
              >
                {submitting ? "Verifying OTP..." : "Verify OTP"}
              </button>
            </div>
          )}

          {/* STEP 3: Set New Password Screen */}
          {step === "reset" && (
            <form onSubmit={handleResetPassword}>
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label className="form-label" style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, display: "block" }}>
                  New Password
                </label>
                <div style={{ position: "relative" }}>
                  <FiLock
                    style={{
                      position: "absolute",
                      left: 14,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                      pointerEvents: "none",
                      fontSize: 16,
                    }}
                  />
                  <input
                    className="form-input"
                    type={showPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    required
                    autoFocus
                    minLength={8}
                    style={{
                      width: "100%",
                      padding: "12px 42px 12px 42px",
                      borderRadius: 12,
                      background: "var(--input-bg, rgba(255, 255, 255, 0.05))",
                      border: "1px solid var(--border-color)",
                      color: "var(--text-primary)",
                      fontSize: 14.5,
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label="Toggle password visibility"
                    style={{
                      position: "absolute",
                      right: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      color: "var(--text-muted)",
                      cursor: "pointer",
                      padding: 4,
                    }}
                  >
                    {showPassword ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                  </button>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 22 }}>
                <label className="form-label" style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, display: "block" }}>
                  Confirm New Password
                </label>
                <div style={{ position: "relative" }}>
                  <FiLock
                    style={{
                      position: "absolute",
                      left: 14,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                      pointerEvents: "none",
                      fontSize: 16,
                    }}
                  />
                  <input
                    className="form-input"
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat new password"
                    required
                    minLength={8}
                    style={{
                      width: "100%",
                      padding: "12px 42px 12px 42px",
                      borderRadius: 12,
                      background: "var(--input-bg, rgba(255, 255, 255, 0.05))",
                      border: "1px solid var(--border-color)",
                      color: "var(--text-primary)",
                      fontSize: 14.5,
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    aria-label="Toggle password visibility"
                    style={{
                      position: "absolute",
                      right: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      color: "var(--text-muted)",
                      cursor: "pointer",
                      padding: 4,
                    }}
                  >
                    {showConfirmPassword ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{
                  width: "100%",
                  padding: "13px",
                  borderRadius: 12,
                  fontSize: 14.5,
                  fontWeight: 600,
                  cursor: submitting ? "not-allowed" : "pointer",
                }}
                disabled={submitting}
              >
                {submitting ? "Updating Password..." : "Reset Password"}
              </button>
            </form>
          )}

          {/* STEP 4: Success confirmation */}
          {step === "done" && (
            <div style={{ textAlign: "center" }}>
              <button
                type="button"
                className="btn btn-primary"
                style={{
                  width: "100%",
                  padding: "13px",
                  borderRadius: 12,
                  fontSize: 14.5,
                  fontWeight: 600,
                }}
                onClick={() => navigate("/login")}
              >
                Proceed to Login
              </button>
            </div>
          )}

          {/* Footer Link */}
          <p style={{ textAlign: "center", fontSize: 13.5, color: "var(--text-secondary)", marginTop: 24, marginBottom: 0 }}>
            Remembered your password?{" "}
            <Link to="/login" style={{ color: "#8b5cf6", fontWeight: 600 }}>
              Back to login
            </Link>
          </p>
        </motion.div>
      </div>
    </PageTransition>
  );
}
