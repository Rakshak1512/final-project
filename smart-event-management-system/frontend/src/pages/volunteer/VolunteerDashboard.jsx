import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import {
  FiCamera,
  FiCheckCircle,
  FiAlertCircle,
  FiX,
  FiUser,
  FiCalendar,
  FiClock,
  FiMapPin,
  FiHash,
  FiUsers,
  FiSearch,
  FiRefreshCw,
  FiShield,
  FiCheck,
  FiUpload,
  FiImage,
  FiRepeat,
  FiDownload,
  FiFileText,
} from "react-icons/fi";
import PageTransition from "../../components/common/PageTransition.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { volunteerService } from "../../api/services.js";
import { generateVolunteerScansPDF } from "../../utils/pdfReportGenerator.js";

export default function VolunteerDashboard() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    volunteer_name: user?.name || "Volunteer",
    volunteer_id: user?.id || 0,
    assigned_events: [],
    today_events: [],
    total_scanned: 0,
    today_scanned: 0,
    recent_scans: [],
  });

  const [eventSearch, setEventSearch] = useState("");
  const [scanSearch, setScanSearch] = useState("");

  // Scanner modal state
  const [scannerOpen, setScannerOpen] = useState(false);
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [manualCode, setManualCode] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifiedAttendee, setVerifiedAttendee] = useState(null);
  const [verifyError, setVerifyError] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmedSuccess, setConfirmedSuccess] = useState(null);

  // Camera & Mode state: Strictly two logical cameras: "back" (default) and "front"
  const [scannerMode, setScannerMode] = useState("camera"); // "camera" | "upload"
  const [cameraChoice, setCameraChoice] = useState("back"); // "back" | "front"
  const [hasFrontCamera, setHasFrontCamera] = useState(true);
  const [hasBackCamera, setHasBackCamera] = useState(true);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [switchingCamera, setSwitchingCamera] = useState(false);

  // References to resolved back & front device IDs (filtered to remove wide/tele/ultra/depth cameras)
  const backCameraIdRef = useRef(null);
  const frontCameraIdRef = useRef(null);

  // Upload QR code state
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadedPreview, setUploadedPreview] = useState(null);
  const [decodingFile, setDecodingFile] = useState(false);

  const fileInputRef = useRef(null);
  const qrScannerRef = useRef(null);
  const html5QrCodeInstance = useRef(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const { data } = await volunteerService.getDashboard();
      setStats(data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not load volunteer dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    return () => {
      stopActiveStream();
    };
  }, []);

  // Completely stop any running camera stream to guarantee only one stream is active at a time
  // and release all camera hardware tracks
  const stopActiveStream = async () => {
    if (html5QrCodeInstance.current) {
      try {
        if (html5QrCodeInstance.current.isScanning) {
          await html5QrCodeInstance.current.stop();
        }
      } catch (e) {
        // Ignore expected teardown errors
      }
    }
    // Also explicitly find any active video elements or media streams and stop all tracks
    try {
      const videoEls = document.querySelectorAll("#qr-reader-box video");
      videoEls.forEach((v) => {
        if (v.srcObject && typeof v.srcObject.getTracks === "function") {
          v.srcObject.getTracks().forEach((track) => {
            try {
              track.stop();
            } catch (err) {}
          });
          v.srcObject = null;
        }
      });
    } catch (e) {}
  };

  // Enumerate cameras and filter exclusively for the primary standard Front and Back cameras
  // Ignores wide-angle, ultra-wide, telephoto, macro, virtual, or depth cameras
  const resolveLogicalCameras = async () => {
    try {
      const { Html5Qrcode } = await import("html5-qrcode");
      const devices = await Html5Qrcode.getCameras();
      if (!devices || devices.length === 0) {
        return { backId: null, frontId: null, frontOk: true, backOk: true };
      }

      const isSpecialLens = (label) => {
        const l = (label || "").toLowerCase();
        return (
          l.includes("wide") ||
          l.includes("ultra") ||
          l.includes("tele") ||
          l.includes("zoom") ||
          l.includes("macro") ||
          l.includes("depth") ||
          l.includes("virtual")
        );
      };

      // 1. Resolve standard Back camera (excluding special auxiliary lenses)
      const standardBack = devices.filter((d) => {
        const l = (d.label || "").toLowerCase();
        return (l.includes("back") || l.includes("rear") || l.includes("environment")) && !isSpecialLens(l);
      });
      const anyBack = standardBack.length > 0
        ? standardBack[0]
        : devices.find((d) => {
            const l = (d.label || "").toLowerCase();
            return l.includes("back") || l.includes("rear") || l.includes("environment");
          });

      // 2. Resolve standard Front camera
      const standardFront = devices.filter((d) => {
        const l = (d.label || "").toLowerCase();
        return (l.includes("front") || l.includes("user") || l.includes("selfie") || l.includes("facetime")) && !isSpecialLens(l);
      });
      const anyFront = standardFront.length > 0
        ? standardFront[0]
        : devices.find((d) => {
            const l = (d.label || "").toLowerCase();
            return l.includes("front") || l.includes("user") || l.includes("selfie") || l.includes("facetime");
          });

      const frontPresent = anyFront !== undefined || (devices.length === 1 && !anyBack);
      const backPresent = anyBack !== undefined || (devices.length === 1 && anyBack !== undefined);

      return {
        backId: anyBack ? anyBack.id : null,
        frontId: anyFront ? anyFront.id : null,
        frontOk: frontPresent,
        backOk: backPresent,
      };
    } catch (e) {
      console.warn("Could not inspect camera devices:", e);
      return { backId: null, frontId: null, frontOk: true, backOk: true };
    }
  };

  // Helper to start the live camera stream for the selected camera choice ("back" or "front")
  const startCameraStream = async (scanner, targetChoice) => {
    const choice = targetChoice || cameraChoice;
    setCameraLoading(true);
    setCameraError(null);

    // Secure context check (camera requires HTTPS or localhost)
    if (!window.isSecureContext && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      setCameraError(
        "Camera access requires a secure connection (HTTPS or localhost). Please use 'Upload QR Image' or manual code entry."
      );
      setCameraLoading(false);
      return;
    }

    // Stop current stream before starting another
    await stopActiveStream();

    // Use specific deviceId if resolved, otherwise facingMode standard constraint
    const primaryConfig = choice === "front"
      ? (frontCameraIdRef.current ? { deviceId: { exact: frontCameraIdRef.current } } : { facingMode: "user" })
      : (backCameraIdRef.current ? { deviceId: { exact: backCameraIdRef.current } } : { facingMode: "environment" });

    const qrConfig = {
      fps: 10,
      qrbox: { width: 250, height: 250 },
      aspectRatio: 1.0,
    };

    try {
      await scanner.start(
        primaryConfig,
        qrConfig,
        (decodedText) => {
          handleVerifyTicket(decodedText);
          try {
            scanner.stop();
          } catch (e) {}
        },
        () => {}
      );
    } catch (err) {
      console.error("Camera scanner start error with primary config:", err);
      // Fallback: try direct facingMode string if deviceId exact match fails
      try {
        const fallbackConfig = { facingMode: choice === "front" ? "user" : "environment" };
        await scanner.start(
          fallbackConfig,
          qrConfig,
          (decodedText) => {
            handleVerifyTicket(decodedText);
            try {
              scanner.stop();
            } catch (e) {}
          },
          () => {}
        );
      } catch (fallbackErr) {
        console.error("Camera scanner fallback error:", fallbackErr);
        let errMsg = "Could not activate camera. Please ensure permissions are granted.";
        const errStr = String(fallbackErr).toLowerCase();
        if (fallbackErr.name === "NotAllowedError" || errStr.includes("permission")) {
          errMsg = "Camera permission was denied. Please allow camera permissions in your browser or switch to 'Upload QR Image'.";
        } else if (fallbackErr.name === "NotFoundError" || errStr.includes("not found")) {
          if (choice === "front") {
            errMsg = "Front camera was not detected on this device. Please use the Back Camera.";
            setHasFrontCamera(false);
          } else {
            errMsg = "Back camera was not detected on this device. You can try the Front Camera or 'Upload QR Image'.";
            setHasBackCamera(false);
          }
        } else if (fallbackErr.name === "NotReadableError" || errStr.includes("in use")) {
          errMsg = "Camera is currently in use by another app or browser tab. Please close other camera apps and retry.";
        }
        setCameraError(errMsg);
      }
    } finally {
      setCameraLoading(false);
    }
  };

  // Initialize or reconfigure camera scanner when modal opens in camera mode
  useEffect(() => {
    let isMounted = true;
    if (scannerOpen && scannerMode === "camera" && !verifiedAttendee && !confirmedSuccess) {
      const startScanner = async () => {
        try {
          const { Html5Qrcode } = await import("html5-qrcode");
          if (!isMounted || !document.getElementById("qr-reader-box")) return;

          // Stop existing stream if any
          await stopActiveStream();

          // Enumerate to pick primary Back & Front cameras (filtering out wide/tele/ultra)
          const { backId, frontId, frontOk, backOk } = await resolveLogicalCameras();
          if (isMounted) {
            backCameraIdRef.current = backId;
            frontCameraIdRef.current = frontId;
            setHasFrontCamera(frontOk);
            setHasBackCamera(backOk);
          }

          const scanner = new Html5Qrcode("qr-reader-box");
          html5QrCodeInstance.current = scanner;

          if (isMounted) {
            // Default to Back camera for QR scanning on mobile & all devices
            const initialChoice = backOk ? "back" : (frontOk ? "front" : "back");
            setCameraChoice(initialChoice);
            await startCameraStream(scanner, initialChoice);
          }
        } catch (e) {
          console.log("Camera scanner initialization error:", e);
        }
      };

      const timer = setTimeout(startScanner, 200);
      return () => {
        isMounted = false;
        clearTimeout(timer);
        stopActiveStream();
      };
    } else {
      stopActiveStream();
    }
  }, [scannerOpen, scannerMode, verifiedAttendee, confirmedSuccess]);

  // Select camera choice directly: strictly "back" or "front"
  const handleSelectCamera = async (targetChoice) => {
    if (switchingCamera || cameraLoading) return;
    if (targetChoice === "front" && !hasFrontCamera) {
      toast.error("Front camera is not available on this device.");
      return;
    }
    if (targetChoice === "back" && !hasBackCamera) {
      toast.error("Back camera is not available on this device.");
      return;
    }
    if (targetChoice === cameraChoice && !cameraError) {
      return; // Already on this camera
    }

    setSwitchingCamera(true);
    setCameraError(null);

    try {
      await stopActiveStream();
      setCameraChoice(targetChoice);

      const { Html5Qrcode } = await import("html5-qrcode");
      let scanner = html5QrCodeInstance.current;
      if (!scanner) {
        scanner = new Html5Qrcode("qr-reader-box");
        html5QrCodeInstance.current = scanner;
      }

      await startCameraStream(scanner, targetChoice);
      toast.success(`Switched to ${targetChoice === "back" ? "Back" : "Front"} Camera`);
    } catch (err) {
      console.error("Camera switch error:", err);
      toast.error("Failed to switch camera.");
    } finally {
      setSwitchingCamera(false);
    }
  };

  // Camera Switch Handler: toggles between Front and Back camera
  const handleSwitchCamera = async () => {
    if (switchingCamera || cameraLoading) return;
    const nextChoice = cameraChoice === "back" ? "front" : "back";
    await handleSelectCamera(nextChoice);
  };

  // QR Image File Upload & Decoding Handler
  const handleFileUpload = async (file) => {
    if (!file) return;

    const validTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp"];
    if (!validTypes.includes(file.type)) {
      toast.error("Please upload a valid image file (PNG, JPG, JPEG, or WebP)");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      toast.error("File size exceeds 10MB limit.");
      return;
    }

    setUploadedFile(file);
    setUploadedPreview(URL.createObjectURL(file));
    setDecodingFile(true);
    setVerifyError(null);

    try {
      // Stop live camera if running
      if (html5QrCodeInstance.current) {
        try {
          if (html5QrCodeInstance.current.isScanning) {
            await html5QrCodeInstance.current.stop();
          }
        } catch (e) {}
      }

      const { Html5Qrcode } = await import("html5-qrcode");
      let scanner = html5QrCodeInstance.current;
      if (!scanner) {
        scanner = new Html5Qrcode("qr-reader-box");
        html5QrCodeInstance.current = scanner;
      }

      const decodedText = await scanner.scanFile(file, true);
      if (decodedText) {
        toast.success("QR Code detected in image!");
        await handleVerifyTicket(decodedText);
      }
    } catch (err) {
      console.error("QR decode from file error:", err);
      setVerifyError(
        "No readable QR code found in this image. Please ensure the QR code is clearly visible, in-focus, and well-lit, or enter the code manually."
      );
    } finally {
      setDecodingFile(false);
    }
  };

  const handleClearUploadedFile = () => {
    setUploadedFile(null);
    if (uploadedPreview) {
      URL.revokeObjectURL(uploadedPreview);
      setUploadedPreview(null);
    }
    setVerifyError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Download Volunteer Scans Log as PDF
  const handleDownloadScansPDF = () => {
    if (!stats.recent_scans || stats.recent_scans.length === 0) {
      toast.error("No scans recorded to generate PDF report.");
      return;
    }
    const targetEvent = stats.assigned_events?.find((e) => e.id === selectedEventId);
    generateVolunteerScansPDF({
      scans: stats.recent_scans,
      volunteerName: stats.volunteer_name,
      volunteerId: stats.volunteer_id,
      eventTitle: targetEvent?.title || null,
    });
    toast.success("Volunteer Attendance Report downloaded as PDF!");
  };

  const handleVerifyTicket = async (ticketPayload) => {
    const code = (ticketPayload || manualCode).trim();
    if (!code) {
      toast.error("Please enter or scan a ticket code");
      return;
    }

    setVerifying(true);
    setVerifyError(null);
    setVerifiedAttendee(null);
    setConfirmedSuccess(null);

    try {
      const { data } = await volunteerService.verifyTicket({
        ticket_code: code,
        event_id: selectedEventId ? parseInt(selectedEventId) : null,
      });
      setVerifiedAttendee(data);
      if (data.already_attended) {
        setVerifyError("⚠️ Attendance has already been confirmed for this student.");
      }
    } catch (err) {
      const detail = err.response?.data?.detail || "Registration not found or invalid QR.";
      setVerifyError(detail);
    } finally {
      setVerifying(false);
    }
  };

  const handleConfirmAttendance = async () => {
    if (!verifiedAttendee) return;
    setConfirming(true);
    try {
      const { data } = await volunteerService.confirmAttendance({
        registration_id: verifiedAttendee.registration_id,
        event_id: verifiedAttendee.event_id,
      });
      toast.success(`Attendance confirmed for ${verifiedAttendee.student_name}!`);
      setConfirmedSuccess(data);
      setVerifiedAttendee(null);
      setVerifyError(null);
      fetchDashboardData();
    } catch (err) {
      const msg = err.response?.data?.detail || "Could not confirm attendance.";
      toast.error(msg);
      setVerifyError(msg);
    } finally {
      setConfirming(false);
    }
  };

  const handleResetScanner = () => {
    setVerifiedAttendee(null);
    setVerifyError(null);
    setConfirmedSuccess(null);
    setManualCode("");
  };

  const openScannerForEvent = (eventId) => {
    setSelectedEventId(eventId);
    handleResetScanner();
    setScannerOpen(true);
  };

  return (
    <PageTransition>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        {/* Header Hero Banner */}
        <div
          className="glass-card float-card"
          style={{
            padding: "32px",
            borderRadius: "24px",
            background: "linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.1) 100%)",
            border: "1.5px solid rgba(139, 92, 246, 0.3)",
            marginBottom: "32px",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              flexWrap: "wrap",
              gap: 20,
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span
                  style={{
                    background: "rgba(139, 92, 246, 0.2)",
                    color: "#a5b4fc",
                    padding: "4px 12px",
                    borderRadius: "999px",
                    fontSize: 12,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <FiShield size={14} /> Volunteer Desk
                </span>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>ID: #{stats.volunteer_id}</span>
              </div>
              <h1 style={{ fontSize: 28, fontWeight: 800, margin: "0 0 8px 0", color: "var(--text-primary)" }}>
                Welcome, {stats.volunteer_name}
              </h1>
              <p style={{ fontSize: 14.5, color: "var(--text-secondary)", margin: 0, maxWidth: 600 }}>
                Scan student QR tickets, verify registrations, and manage contactless attendee entry for campus events.
              </p>
            </div>

            {/* Quick Action Button */}
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => {
                setSelectedEventId(null);
                handleResetScanner();
                setScannerOpen(true);
              }}
              className="btn btn-primary"
              style={{
                padding: "14px 28px",
                fontSize: 16,
                fontWeight: 700,
                borderRadius: 16,
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                boxShadow: "0 10px 25px rgba(139, 92, 246, 0.4)",
              }}
            >
              <FiCamera size={20} />
              Scan Registration QR
            </motion.button>
          </div>
        </div>

        {/* Stats Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 20,
            marginBottom: 32,
          }}
        >
          <div
            className="glass-card"
            style={{
              padding: "24px",
              borderRadius: "20px",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-color)",
              display: "flex",
              alignItems: "center",
              gap: 18,
            }}
          >
            <div
              style={{
                width: 54,
                height: 54,
                borderRadius: 16,
                background: "rgba(16, 185, 129, 0.15)",
                color: "#10b981",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
              }}
            >
              <FiCheckCircle />
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>Total Scanned</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-primary)" }}>{stats.total_scanned}</div>
            </div>
          </div>

          <div
            className="glass-card"
            style={{
              padding: "24px",
              borderRadius: "20px",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-color)",
              display: "flex",
              alignItems: "center",
              gap: 18,
            }}
          >
            <div
              style={{
                width: 54,
                height: 54,
                borderRadius: 16,
                background: "rgba(139, 92, 246, 0.15)",
                color: "#8b5cf6",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
              }}
            >
              <FiClock />
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>Scanned Today</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-primary)" }}>{stats.today_scanned}</div>
            </div>
          </div>

          <div
            className="glass-card"
            style={{
              padding: "24px",
              borderRadius: "20px",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-color)",
              display: "flex",
              alignItems: "center",
              gap: 18,
            }}
          >
            <div
              style={{
                width: 54,
                height: 54,
                borderRadius: 16,
                background: "rgba(14, 165, 233, 0.15)",
                color: "#0ea5e9",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
              }}
            >
              <FiCalendar />
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>Active Events</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-primary)" }}>
                {stats.assigned_events?.length || 0}
              </div>
            </div>
          </div>
        </div>

        {/* Assigned & Today's Events Grid */}
        <div style={{ marginBottom: 40 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 4px 0" }}>Active Campus Events</h2>
              <p style={{ fontSize: 13.5, color: "var(--text-secondary)", margin: 0 }}>
                Select an event to restrict scanning or launch check-in desk
              </p>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              {stats.assigned_events && stats.assigned_events.length > 0 && (
                <div style={{ position: "relative", minWidth: 0, width: "100%", maxWidth: 360 }}>
                  <input
                    className="form-input"
                    style={{ padding: "8px 34px 8px 34px", fontSize: 13 }}
                    placeholder="Search events, venue, category..."
                    value={eventSearch}
                    onChange={(e) => setEventSearch(e.target.value)}
                  />
                  <FiSearch
                    size={14}
                    style={{
                      position: "absolute",
                      left: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                      pointerEvents: "none",
                    }}
                  />
                  {eventSearch && (
                    <button
                      type="button"
                      onClick={() => setEventSearch("")}
                      style={{
                        position: "absolute",
                        right: 12,
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        padding: 2,
                      }}
                      title="Clear search"
                    >
                      <FiX size={14} />
                    </button>
                  )}
                </div>
              )}
              <button
                onClick={fetchDashboardData}
                className="btn btn-outline btn-sm"
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                <FiRefreshCw size={14} /> Refresh
              </button>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
              gap: 20,
            }}
          >
            {(() => {
              const filteredEvents = (stats.assigned_events || []).filter((ev) => {
                if (!eventSearch.trim()) return true;
                const q = eventSearch.trim().toLowerCase();
                return (
                  (ev.title || "").toLowerCase().includes(q) ||
                  (ev.category || "").toLowerCase().includes(q) ||
                  (ev.venue || "").toLowerCase().includes(q)
                );
              });

              if (filteredEvents.length === 0 && (stats.assigned_events || []).length > 0) {
                return (
                  <div style={{ gridColumn: "1 / -1", padding: "36px", textAlign: "center", background: "var(--bg-elevated)", borderRadius: "20px", border: "1px dashed var(--border-color)" }}>
                    <p style={{ color: "var(--text-secondary)", margin: "0 0 10px" }}>
                      No events matched "{eventSearch}".
                    </p>
                    <button className="btn btn-outline btn-sm" onClick={() => setEventSearch("")}>
                      Clear Search
                    </button>
                  </div>
                );
              }

              if (filteredEvents.length === 0) {
                return (
                  <div style={{ gridColumn: "1 / -1", padding: "36px", textAlign: "center", background: "var(--bg-elevated)", borderRadius: "20px", border: "1px dashed var(--border-color)" }}>
                    <p style={{ color: "var(--text-secondary)", margin: 0 }}>
                      No campus events scheduled for today. You can still scan valid passes using the universal QR scanner.
                    </p>
                  </div>
                );
              }

              return filteredEvents.map((ev) => {
                const pct = ev.registered > 0 ? Math.round((ev.checked_in / ev.registered) * 100) : 0;
                return (
                  <div
                    key={ev.id}
                    className="glass-card"
                    style={{
                      padding: "20px",
                      borderRadius: "20px",
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border-color)",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                        <span
                          style={{
                            fontSize: 11.5,
                            fontWeight: 700,
                            padding: "3px 10px",
                            borderRadius: 999,
                            background: "rgba(139, 92, 246, 0.15)",
                            color: "#a5b4fc",
                            textTransform: "uppercase",
                          }}
                        >
                          {ev.category}
                        </span>
                        <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                          {ev.remaining} remaining
                        </span>
                      </div>

                      <h3 style={{ fontSize: 17, fontWeight: 700, margin: "0 0 10px 0", color: "var(--text-primary)" }}>
                        {ev.title}
                      </h3>

                      <div style={{ fontSize: 13, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <FiCalendar size={14} color="#8b5cf6" /> {ev.event_date} ({ev.event_time})
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <FiMapPin size={14} color="#8b5cf6" /> {ev.venue}
                        </div>
                      </div>

                      {/* Progress Bar */}
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
                          <span style={{ color: "var(--text-muted)" }}>Checked In</span>
                          <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                            {ev.checked_in} / {ev.registered} ({pct}%)
                          </span>
                        </div>
                        <div style={{ height: 8, background: "var(--border-color)", borderRadius: 999, overflow: "hidden" }}>
                          <div
                            style={{
                              width: `${pct}%`,
                              height: "100%",
                              background: "var(--gradient-primary)",
                              borderRadius: 999,
                              transition: "width 0.5s ease",
                            }}
                          />
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => openScannerForEvent(ev.id)}
                      className="btn btn-outline btn-sm"
                      style={{
                        width: "100%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 8,
                        fontWeight: 600,
                      }}
                    >
                      <FiCamera size={15} /> Scan Attendees for this Event
                    </button>
                  </div>
                );
              });
            })()}
          </div>
        </div>

        {/* Scan History Table */}
        <div
          className="glass-card"
          style={{
            padding: "24px",
            borderRadius: "24px",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-color)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Recent Scans Log</h2>
              {stats.recent_scans && stats.recent_scans.length > 0 && (
                <span className="badge badge-info">{stats.recent_scans.length} Verified</span>
              )}
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              {stats.recent_scans && stats.recent_scans.length > 0 && (
                <button
                  type="button"
                  onClick={handleDownloadScansPDF}
                  className="btn btn-sm btn-outline"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "7px 14px",
                    borderRadius: 10,
                    fontSize: 12.5,
                    fontWeight: 600,
                  }}
                  title="Download Attendance Scans Log as PDF"
                >
                  <FiDownload size={14} /> Download Scans PDF
                </button>
              )}
              {stats.recent_scans && stats.recent_scans.length > 0 && (
                <div style={{ position: "relative", minWidth: 0, width: "100%", maxWidth: 360 }}>
                  <input
                    className="form-input"
                    style={{ padding: "8px 34px 8px 34px", fontSize: 13 }}
                    placeholder="Search student, reg no, event..."
                    value={scanSearch}
                    onChange={(e) => setScanSearch(e.target.value)}
                  />
                  <FiSearch
                    size={14}
                    style={{
                      position: "absolute",
                      left: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                      pointerEvents: "none",
                    }}
                  />
                  {scanSearch && (
                    <button
                      type="button"
                      onClick={() => setScanSearch("")}
                      style={{
                        position: "absolute",
                        right: 10,
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        padding: 2,
                      }}
                      title="Clear search"
                    >
                      <FiX size={14} />
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {(() => {
            const filteredScans = (stats.recent_scans || []).filter((scan) => {
              if (!scanSearch.trim()) return true;
              const q = scanSearch.trim().toLowerCase();
              return (
                (scan.student_name || "").toLowerCase().includes(q) ||
                (scan.registration_number || "").toLowerCase().includes(q) ||
                (scan.event_title || "").toLowerCase().includes(q)
              );
            });

            if (stats.recent_scans && stats.recent_scans.length > 0) {
              if (filteredScans.length === 0) {
                return (
                  <div style={{ padding: "30px", textAlign: "center", color: "var(--text-secondary)" }}>
                    No scans matching "{scanSearch}".
                  </div>
                );
              }

              return (
                <div className="table-wrap" style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5, textAlign: "left" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-color)", color: "var(--text-secondary)" }}>
                        <th style={{ padding: "12px 16px" }}>Student</th>
                        <th style={{ padding: "12px 16px" }}>Reg No</th>
                        <th style={{ padding: "12px 16px" }}>Event</th>
                        <th style={{ padding: "12px 16px" }}>Check-in Time</th>
                        <th style={{ padding: "12px 16px" }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredScans.map((scan, idx) => (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: "1px solid var(--border-color)",
                        transition: "background 0.2s ease",
                      }}
                    >
                      <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text-primary)" }}>
                        {scan.student_name}
                      </td>
                      <td style={{ padding: "14px 16px", fontFamily: "monospace", color: "#a5b4fc" }}>
                        {scan.registration_number || "N/A"}
                      </td>
                      <td style={{ padding: "14px 16px", color: "var(--text-secondary)" }}>
                        {scan.event_title}
                      </td>
                      <td style={{ padding: "14px 16px", color: "var(--text-muted)", fontSize: 12.5 }}>
                        {scan.scanned_at}
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <span
                          style={{
                            padding: "4px 10px",
                            borderRadius: 999,
                            background: "rgba(16, 185, 129, 0.15)",
                            color: "#10b981",
                            fontWeight: 700,
                            fontSize: 12,
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <FiCheck size={12} /> Present
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

            return (
              <div style={{ textAlign: "center", padding: "32px", color: "var(--text-muted)" }}>
                No check-in activity recorded yet. Scans confirmed by you will appear here in real-time.
              </div>
            );
          })()}
        </div>

        {/* QR SCANNER & ATTENDEE VERIFICATION MODAL */}
        <AnimatePresence>
          {scannerOpen && (
            <div
              style={{
                position: "fixed",
                inset: 0,
                background: "rgba(3, 7, 18, 0.8)",
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 999,
                padding: "calc(env(safe-area-inset-top, 16px) + 10px) calc(env(safe-area-inset-right, 16px) + 8px) calc(env(safe-area-inset-bottom, 16px) + 10px) calc(env(safe-area-inset-left, 16px) + 8px)",
                boxSizing: "border-box",
              }}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 20 }}
                className="glass-card"
                style={{
                  width: "100%",
                  maxWidth: 540,
                  background: "var(--bg-elevated)",
                  borderRadius: 24,
                  border: "1.5px solid rgba(139, 92, 246, 0.3)",
                  boxShadow: "0 25px 60px rgba(0,0,0,0.5)",
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                  maxHeight: "calc(100dvh - 36px)",
                  boxSizing: "border-box",
                }}
              >
                {/* Modal Header */}
                <div
                  style={{
                    padding: "clamp(12px, 3vw, 20px) clamp(14px, 3.5vw, 24px)",
                    borderBottom: "1px solid var(--border-color)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    background: "var(--bg-glass)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        background: "var(--gradient-primary)",
                        color: "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <FiCamera size={18} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Registration QR Scanner</h3>
                      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
                        {selectedEventId
                          ? `Restricted to Event #${selectedEventId}`
                          : "Scanning for all active campus events"}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      stopActiveStream();
                      setScannerOpen(false);
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                      padding: 4,
                    }}
                  >
                    <FiX size={20} />
                  </button>
                </div>

                {/* Modal Body */}
                <div style={{ padding: "clamp(14px, 3.5vw, 24px)", overflowY: "auto" }}>
                  {/* STATE 1: SUCCESS CONFIRMATION */}
                  {confirmedSuccess && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      style={{ textAlign: "center", padding: "20px 0" }}
                    >
                      <div
                        style={{
                          width: 72,
                          height: 72,
                          borderRadius: "50%",
                          background: "rgba(16, 185, 129, 0.15)",
                          color: "#10b981",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 36,
                          margin: "0 auto 16px",
                          border: "2px solid #10b981",
                        }}
                      >
                        <FiCheck />
                      </div>
                      <h3 style={{ fontSize: 22, fontWeight: 800, color: "#10b981", margin: "0 0 6px 0" }}>
                        Attendance Confirmed!
                      </h3>
                      <p style={{ fontSize: 14.5, color: "var(--text-primary)", fontWeight: 600, margin: "0 0 4px 0" }}>
                        {confirmedSuccess.student_name} ({confirmedSuccess.registration_number || "Student"})
                      </p>
                      <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "0 0 20px 0" }}>
                        {confirmedSuccess.event_title} • {confirmedSuccess.checked_in_at}
                      </p>
                      <button
                        onClick={handleResetScanner}
                        className="btn btn-primary"
                        style={{ width: "100%", padding: "12px", fontSize: 15, fontWeight: 700, borderRadius: 12 }}
                      >
                        Scan Next Attendee
                      </button>
                    </motion.div>
                  )}

                  {/* STATE 2: ATTENDEE VERIFIED (CONFIRMATION PROMPT) */}
                  {!confirmedSuccess && verifiedAttendee && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                      <div
                        style={{
                          background: "var(--bg-base)",
                          borderRadius: 16,
                          padding: "20px",
                          border: "1px solid var(--border-color)",
                          marginBottom: 20,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                          <div>
                            <span style={{ fontSize: 11.5, color: "var(--text-muted)", textTransform: "uppercase" }}>
                              Attendee Verification
                            </span>
                            <h4 style={{ fontSize: 18, fontWeight: 800, margin: "2px 0 0 0", color: "var(--text-primary)" }}>
                              {verifiedAttendee.student_name}
                            </h4>
                          </div>
                          <span
                            style={{
                              padding: "4px 10px",
                              borderRadius: 999,
                              background: verifiedAttendee.already_attended ? "rgba(239, 68, 68, 0.15)" : "rgba(16, 185, 129, 0.15)",
                              color: verifiedAttendee.already_attended ? "#ef4444" : "#10b981",
                              fontSize: 12,
                              fontWeight: 700,
                            }}
                          >
                            {verifiedAttendee.already_attended ? "Already Checked In" : "Valid Pass"}
                          </span>
                        </div>

                        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
                          <tbody>
                            <tr>
                              <td style={{ color: "var(--text-muted)", padding: "4px 0" }}>Reg No:</td>
                              <td style={{ color: "var(--text-primary)", fontWeight: 600, fontFamily: "monospace" }}>
                                {verifiedAttendee.registration_number || "N/A"}
                              </td>
                            </tr>
                            <tr>
                              <td style={{ color: "var(--text-muted)", padding: "4px 0" }}>Department:</td>
                              <td style={{ color: "var(--text-primary)" }}>{verifiedAttendee.department || "N/A"}</td>
                            </tr>
                            <tr>
                              <td style={{ color: "var(--text-muted)", padding: "4px 0" }}>Event:</td>
                              <td style={{ color: "var(--text-primary)", fontWeight: 600 }}>{verifiedAttendee.event_title}</td>
                            </tr>
                            <tr>
                              <td style={{ color: "var(--text-muted)", padding: "4px 0" }}>Date & Venue:</td>
                              <td style={{ color: "var(--text-secondary)" }}>
                                {verifiedAttendee.event_date} ({verifiedAttendee.venue})
                              </td>
                            </tr>
                            {verifiedAttendee.team_name && (
                              <tr>
                                <td style={{ color: "var(--text-muted)", padding: "4px 0" }}>Team:</td>
                                <td style={{ color: "var(--text-primary)", fontWeight: 600 }}>{verifiedAttendee.team_name}</td>
                              </tr>
                            )}
                            <tr>
                              <td style={{ color: "var(--text-muted)", padding: "4px 0" }}>Ticket Code:</td>
                              <td style={{ fontFamily: "monospace", color: "#a5b4fc" }}>#{verifiedAttendee.ticket_code}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      {verifiedAttendee.already_attended ? (
                        <div
                          style={{
                            padding: "14px",
                            borderRadius: 12,
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "1px solid rgba(239, 68, 68, 0.3)",
                            color: "#fca5a5",
                            fontSize: 13,
                            marginBottom: 20,
                          }}
                        >
                          ⚠️ Attendance was already confirmed at {verifiedAttendee.checked_in_at || "previously"} by{" "}
                          {verifiedAttendee.checked_in_by || "staff"}.
                        </div>
                      ) : null}

                      <div style={{ display: "flex", gap: 12 }}>
                        <button
                          onClick={handleResetScanner}
                          className="btn btn-outline"
                          style={{ flex: 1, padding: "12px", borderRadius: 12 }}
                        >
                          Cancel / Scan Next
                        </button>
                        <button
                          onClick={handleConfirmAttendance}
                          disabled={confirming || verifiedAttendee.already_attended}
                          className="btn btn-primary"
                          style={{
                            flex: 2,
                            padding: "12px",
                            borderRadius: 12,
                            fontWeight: 700,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 8,
                          }}
                        >
                          {confirming ? "Confirming..." : "✓ Confirm Attendance"}
                        </button>
                      </div>
                    </motion.div>
                  )}

                  {/* STATE 3: LIVE SCANNER / CODE ENTRY */}
                  {!confirmedSuccess && !verifiedAttendee && (
                    <div>
                      {/* Mode Switcher Tabs */}
                      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                        <button
                          type="button"
                          onClick={() => {
                            setScannerMode("camera");
                            setVerifyError(null);
                          }}
                          className="btn btn-sm"
                          style={{
                            flex: 1,
                            padding: "8px 12px",
                            borderRadius: 10,
                            background: scannerMode === "camera" ? "var(--gradient-primary)" : "var(--bg-glass)",
                            color: scannerMode === "camera" ? "#ffffff" : "var(--text-secondary)",
                            border: scannerMode === "camera" ? "none" : "1px solid var(--border-color)",
                            fontWeight: 600,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 6,
                          }}
                        >
                          <FiCamera size={15} /> Live Camera Scan
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setScannerMode("upload");
                            setVerifyError(null);
                          }}
                          className="btn btn-sm"
                          style={{
                            flex: 1,
                            padding: "8px 12px",
                            borderRadius: 10,
                            background: scannerMode === "upload" ? "var(--gradient-primary)" : "var(--bg-glass)",
                            color: scannerMode === "upload" ? "#ffffff" : "var(--text-secondary)",
                            border: scannerMode === "upload" ? "none" : "1px solid var(--border-color)",
                            fontWeight: 600,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 6,
                          }}
                        >
                          <FiUpload size={15} /> Upload QR Image
                        </button>
                      </div>

                      {/* MODE A: LIVE CAMERA */}
                      {scannerMode === "camera" && (
                        <div>
                          {/* Camera Controls Toolbar: Exclusively Front Camera & Back Camera */}
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: 10,
                              marginBottom: 12,
                              padding: "0 2px",
                            }}
                          >
                            {/* Strictly two options: Back Camera and Front Camera */}
                            <div
                              style={{
                                display: "inline-flex",
                                gap: 4,
                                background: "var(--bg-glass)",
                                padding: 4,
                                borderRadius: 12,
                                border: "1px solid var(--border-color)",
                              }}
                            >
                              <button
                                type="button"
                                onClick={() => handleSelectCamera("back")}
                                disabled={switchingCamera || cameraLoading || !hasBackCamera}
                                style={{
                                  padding: "6px 14px",
                                  borderRadius: 8,
                                  fontSize: 12.5,
                                  fontWeight: cameraChoice === "back" ? 700 : 500,
                                  background: cameraChoice === "back" ? "var(--gradient-primary)" : "transparent",
                                  color: cameraChoice === "back" ? "#ffffff" : "var(--text-secondary)",
                                  border: "none",
                                  cursor: hasBackCamera ? "pointer" : "not-allowed",
                                  opacity: hasBackCamera ? 1 : 0.45,
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 6,
                                  transition: "all 0.2s ease",
                                }}
                                title="Use Back Camera (Recommended for QR scanning)"
                              >
                                <FiCamera size={14} /> Back Camera
                              </button>

                              <button
                                type="button"
                                onClick={() => handleSelectCamera("front")}
                                disabled={switchingCamera || cameraLoading || !hasFrontCamera}
                                style={{
                                  padding: "6px 14px",
                                  borderRadius: 8,
                                  fontSize: 12.5,
                                  fontWeight: cameraChoice === "front" ? 700 : 500,
                                  background: cameraChoice === "front" ? "var(--gradient-primary)" : "transparent",
                                  color: cameraChoice === "front" ? "#ffffff" : "var(--text-secondary)",
                                  border: "none",
                                  cursor: hasFrontCamera ? "pointer" : "not-allowed",
                                  opacity: hasFrontCamera ? 1 : 0.45,
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 6,
                                  transition: "all 0.2s ease",
                                }}
                                title={hasFrontCamera ? "Use Front Camera" : "Front camera not detected on this device"}
                              >
                                <FiUser size={14} /> Front Camera
                                {!hasFrontCamera && (
                                  <span style={{ fontSize: 10, opacity: 0.7 }}>(N/A)</span>
                                )}
                              </button>
                            </div>

                            {/* Switch Camera Button */}
                            <button
                              type="button"
                              onClick={handleSwitchCamera}
                              disabled={switchingCamera || cameraLoading || (!hasFrontCamera && !hasBackCamera)}
                              className="btn btn-sm btn-outline"
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 6,
                                padding: "7px 14px",
                                borderRadius: 10,
                                fontSize: 12.5,
                                fontWeight: 600,
                                minHeight: 34,
                              }}
                              title="Toggle between Front and Back camera"
                            >
                              <FiRepeat size={13} className={switchingCamera ? "spin-icon" : ""} />
                              {switchingCamera ? "Switching..." : "Switch Camera"}
                            </button>
                          </div>

                          {/* Active Camera Indicator */}
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: 10,
                              fontSize: 12,
                              color: "var(--text-secondary)",
                              padding: "0 2px",
                            }}
                          >
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                              <span
                                style={{
                                  width: 8,
                                  height: 8,
                                  borderRadius: "50%",
                                  background: cameraError ? "var(--danger)" : "#10b981",
                                  boxShadow: cameraError
                                    ? "0 0 8px rgba(239, 68, 68, 0.6)"
                                    : "0 0 8px rgba(16, 185, 129, 0.6)",
                                  display: "inline-block",
                                }}
                              />
                              {cameraError
                                ? "Camera Inactive"
                                : cameraChoice === "back"
                                ? "Active: Back Camera (Default for QR)"
                                : "Active: Front Camera"}
                            </span>

                            {!hasFrontCamera && (
                              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                                Front camera unavailable on this device
                              </span>
                            )}
                          </div>

                          {/* Error Notice with Quick Actions */}
                          {cameraError && (
                            <div
                              style={{
                                padding: "14px",
                                borderRadius: 14,
                                background: "rgba(239, 68, 68, 0.1)",
                                border: "1px solid rgba(239, 68, 68, 0.3)",
                                color: "#fca5a5",
                                fontSize: 12.5,
                                marginBottom: 14,
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, marginBottom: 4 }}>
                                <FiAlertCircle size={15} /> Camera Notice
                              </div>
                              <div style={{ marginBottom: 10 }}>{cameraError}</div>
                              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                <button
                                  type="button"
                                  onClick={() => handleSelectCamera(cameraChoice)}
                                  className="btn btn-sm btn-outline"
                                  style={{ fontSize: 11.5, padding: "5px 12px", borderColor: "rgba(239, 68, 68, 0.4)" }}
                                >
                                  <FiRefreshCw size={12} /> Retry Camera
                                </button>
                                <button
                                  type="button"
                                  onClick={handleSwitchCamera}
                                  className="btn btn-sm btn-outline"
                                  style={{ fontSize: 11.5, padding: "5px 12px", borderColor: "rgba(239, 68, 68, 0.4)" }}
                                >
                                  <FiRepeat size={12} /> Switch to {cameraChoice === "back" ? "Front" : "Back"} Camera
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setScannerMode("upload")}
                                  className="btn btn-sm btn-primary"
                                  style={{ fontSize: 11.5, padding: "5px 12px" }}
                                >
                                  <FiUpload size={12} /> Upload QR Image Instead
                                </button>
                              </div>
                            </div>
                          )}

                          {/* Live Camera Viewfinder Box */}
                          <div
                            id="qr-reader-box"
                            style={{
                              width: "100%",
                              minHeight: 250,
                              background: "#000",
                              borderRadius: 16,
                              overflow: "hidden",
                              marginBottom: 16,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              border: "1.5px dashed rgba(139, 92, 246, 0.4)",
                            }}
                          />
                        </div>
                      )}

                      {/* MODE B: UPLOAD QR IMAGE */}
                      {scannerMode === "upload" && (
                        <div>
                          <input
                            type="file"
                            ref={fileInputRef}
                            accept="image/png, image/jpeg, image/jpg, image/webp"
                            style={{ display: "none" }}
                            onChange={(e) => {
                              if (e.target.files && e.target.files[0]) {
                                handleFileUpload(e.target.files[0]);
                              }
                            }}
                          />

                          {!uploadedPreview ? (
                            <div
                              onClick={() => fileInputRef.current?.click()}
                              onDragOver={(e) => e.preventDefault()}
                              onDrop={(e) => {
                                e.preventDefault();
                                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                                  handleFileUpload(e.dataTransfer.files[0]);
                                }
                              }}
                              style={{
                                border: "2px dashed rgba(139, 92, 246, 0.5)",
                                borderRadius: 16,
                                padding: "32px 16px",
                                textAlign: "center",
                                cursor: "pointer",
                                background: "rgba(139, 92, 246, 0.05)",
                                transition: "all 0.2s ease",
                                marginBottom: 16,
                              }}
                            >
                              <div
                                style={{
                                  width: 48,
                                  height: 48,
                                  borderRadius: "50%",
                                  background: "rgba(139, 92, 246, 0.15)",
                                  color: "#8b5cf6",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  margin: "0 auto 10px",
                                  fontSize: 22,
                                }}
                              >
                                <FiUpload />
                              </div>
                              <h4 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 4px 0", color: "var(--text-primary)" }}>
                                Select or Drop QR Code Image
                              </h4>
                              <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "0 0 10px 0" }}>
                                Tap to pick from gallery or drag a QR code screenshot here
                              </p>
                              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                                PNG, JPG, JPEG, and WebP (up to 10MB)
                              </span>
                            </div>
                          ) : (
                            <div
                              style={{
                                borderRadius: 16,
                                padding: 14,
                                background: "var(--bg-glass)",
                                border: "1px solid var(--border-color)",
                                marginBottom: 16,
                                display: "flex",
                                alignItems: "center",
                                gap: 14,
                              }}
                            >
                              <img
                                src={uploadedPreview}
                                alt="QR Preview"
                                style={{
                                  width: 72,
                                  height: 72,
                                  objectFit: "cover",
                                  borderRadius: 12,
                                  border: "1px solid var(--border-color)",
                                }}
                              />
                              <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", marginBottom: 2 }}>
                                  {uploadedFile?.name || "QR Image"}
                                </div>
                                <div style={{ fontSize: 11.5, color: "var(--text-secondary)", marginBottom: 8 }}>
                                  {decodingFile ? (
                                    <span style={{ color: "#8b5cf6", display: "inline-flex", alignItems: "center", gap: 4 }}>
                                      <FiRefreshCw className="spin-icon" size={12} /> Analyzing QR Code...
                                    </span>
                                  ) : (
                                    "Image ready for validation"
                                  )}
                                </div>
                                <button
                                  type="button"
                                  onClick={handleClearUploadedFile}
                                  className="btn btn-sm btn-outline"
                                  style={{ fontSize: 11.5, padding: "4px 10px", borderRadius: 8 }}
                                >
                                  Remove / Replace Image
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {verifyError && (
                        <div
                          style={{
                            padding: "12px 16px",
                            borderRadius: 12,
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "1px solid rgba(239, 68, 68, 0.3)",
                            color: "#fca5a5",
                            fontSize: 13,
                            marginBottom: 16,
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                          }}
                        >
                          <FiAlertCircle size={16} /> {verifyError}
                        </div>
                      )}

                      {/* Manual Code Input Fallback */}
                      <div>
                        <label style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6, display: "block" }}>
                          Or Enter Ticket Code Manually
                        </label>
                        <div style={{ display: "flex", gap: 8 }}>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g. ESP-123456 or REG-123"
                            value={manualCode}
                            onChange={(e) => setManualCode(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleVerifyTicket();
                            }}
                            style={{ flex: 1 }}
                          />
                          <button
                            type="button"
                            onClick={() => handleVerifyTicket()}
                            disabled={verifying || !manualCode.trim()}
                            className="btn btn-primary"
                            style={{ padding: "0 18px", fontWeight: 600 }}
                          >
                            {verifying ? "Verifying..." : "Verify"}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            </div>
          )}
        </AnimatePresence>
      </div>
    </PageTransition>
  );
}
