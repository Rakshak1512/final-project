import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import {
  FiDownload,
  FiCheck,
  FiUpload,
  FiRefreshCw,
  FiImage,
  FiEye,
  FiSliders,
  FiAward,
  FiCalendar,
  FiClock,
  FiMapPin,
  FiUser,
  FiFileText,
} from "react-icons/fi";
import { HiSparkles } from "react-icons/hi";
import { jsPDF } from "jspdf";

const TEMPLATES = [
  {
    id: "tech_cyber",
    name: "Cyber Tech Matrix",
    category: "Technical",
    categoryMatch: ["technical", "tech", "coding", "hackathon", "ai", "robotics", "computer"],
    bgPrimary: "#070b19",
    bgSecondary: "#1e1b4b",
    accentColor: "#06b6d4",
    accentSecondary: "#8b5cf6",
    textColor: "#f8fafc",
    badgeText: "CAMPUS TECH SUMMIT & HACKATHON",
    pattern: "cyber",
    fontFamily: "Space Grotesk, sans-serif",
  },
  {
    id: "cultural_neon",
    name: "Vibrant Neon Glow",
    category: "Cultural",
    categoryMatch: ["cultural", "arts", "music", "dance", "drama", "fest", "carnival"],
    bgPrimary: "#180226",
    bgSecondary: "#581c87",
    accentColor: "#f43f5e",
    accentSecondary: "#e879f9",
    textColor: "#ffffff",
    badgeText: "ANNUAL CULTURAL SHOWCASE & FEST",
    pattern: "neon_waves",
    fontFamily: "Outfit, sans-serif",
  },
  {
    id: "sports_pulse",
    name: "Dynamic Sports Pulse",
    category: "Sports",
    categoryMatch: ["sports", "athletic", "cricket", "football", "fitness", "tournament", "esports"],
    bgPrimary: "#09090b",
    bgSecondary: "#7c2d12",
    accentColor: "#f97316",
    accentSecondary: "#eab308",
    textColor: "#ffffff",
    badgeText: "CHAMPIONSHIP ATHLETIC SERIES",
    pattern: "kinetic_chevrons",
    fontFamily: "Plus Jakarta Sans, sans-serif",
  },
  {
    id: "academic_summit",
    name: "Executive Academic Summit",
    category: "Academic",
    categoryMatch: ["academic", "seminar", "conference", "research", "symposium", "lecture"],
    bgPrimary: "#022c22",
    bgSecondary: "#0f172a",
    accentColor: "#10b981",
    accentSecondary: "#38bdf8",
    textColor: "#f0fdf4",
    badgeText: "DISTINGUISHED SPEAKER CONFERENCE",
    pattern: "minimal_circles",
    fontFamily: "Inter, sans-serif",
  },
  {
    id: "minimal_luxe",
    name: "Modern Minimal Luxe",
    category: "General",
    categoryMatch: ["workshop", "general", "meetup", "orientation", "club", "other"],
    bgPrimary: "#09090b",
    bgSecondary: "#1f1d2b",
    accentColor: "#8b5cf6",
    accentSecondary: "#ec4899",
    textColor: "#f8fafc",
    badgeText: "SPECIAL CAMPUS EVENT",
    pattern: "gradient_mesh",
    fontFamily: "Outfit, sans-serif",
  },
];

export default function EventPosterDesigner({
  eventForm,
  onApplyPoster,
  existingPosterUrl = null,
}) {
  const canvasRef = useRef(null);

  // Active Designer Controls
  const [selectedTemplateId, setSelectedTemplateId] = useState("tech_cyber");
  const [aspectRatio, setAspectRatio] = useState("banner"); // 'banner' (16:9) | 'flyer' (4:5)
  const [headline, setHeadline] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [badgeText, setBadgeText] = useState("");
  const [organizerText, setOrganizerText] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#070b19");
  const [secondaryColor, setSecondaryColor] = useState("#1e1b4b");
  const [accentColor, setAccentColor] = useState("#06b6d4");
  const [textColor, setTextColor] = useState("#f8fafc");
  const [showBranding, setShowBranding] = useState(true);
  const [align, setAlign] = useState("center"); // 'center' | 'left'
  const [customBgImage, setCustomBgImage] = useState(null);
  const [customLogo, setCustomLogo] = useState(null);

  // Export & preview state
  const [exporting, setExporting] = useState(false);
  const [applied, setApplied] = useState(false);
  const [activeTab, setActiveTab] = useState("templates"); // 'templates' | 'colors' | 'content' | 'assets'

  // Initialize or auto-select template based on event form category
  const selectTemplateForCategory = useCallback(
    (cat) => {
      const cleanCat = String(cat || "").toLowerCase();
      const match = TEMPLATES.find((t) => t.categoryMatch.some((k) => cleanCat.includes(k))) || TEMPLATES[0];
      setSelectedTemplateId(match.id);
      setPrimaryColor(match.bgPrimary);
      setSecondaryColor(match.bgSecondary);
      setAccentColor(match.accentColor);
      setBadgeText(match.badgeText);
      setTextColor(match.textColor);
    },
    []
  );

  // Sync with event form changes
  useEffect(() => {
    if (eventForm.title && (!headline || headline === "ANNUAL CAMPUS EVENT")) {
      setHeadline(eventForm.title);
    }
    if (eventForm.description && (!subtitle || subtitle === "Join us for an inspiring campus experience.")) {
      setSubtitle(eventForm.description.slice(0, 140));
    }
    if (eventForm.organizer_name) {
      setOrganizerText(eventForm.organizer_name);
    }
  }, [eventForm.title, eventForm.description, eventForm.organizer_name]);

  // Initial category detection
  useEffect(() => {
    selectTemplateForCategory(eventForm.category || "Technical");
    if (eventForm.title) setHeadline(eventForm.title);
    if (eventForm.description) setSubtitle(eventForm.description.slice(0, 140));
    if (eventForm.organizer_name) setOrganizerText(eventForm.organizer_name);
  }, []);

  // Handle template selection
  const handleApplyTemplate = (tmpl) => {
    setSelectedTemplateId(tmpl.id);
    setPrimaryColor(tmpl.bgPrimary);
    setSecondaryColor(tmpl.bgSecondary);
    setAccentColor(tmpl.accentColor);
    setBadgeText(tmpl.badgeText);
    setTextColor(tmpl.textColor);
    toast.success(`Applied ${tmpl.name} theme`);
  };

  // Draw the high-resolution poster canvas
  const drawPoster = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas dimensions (2x scale for ultra crisp text and high-res export)
    const width = aspectRatio === "flyer" ? 1080 : 1360;
    const height = aspectRatio === "flyer" ? 1350 : 765;
    canvas.width = width;
    canvas.height = height;

    // 1. Draw Multi-Stop Background Gradient
    const bgGrad = ctx.createLinearGradient(0, 0, width, height);
    bgGrad.addColorStop(0, primaryColor);
    bgGrad.addColorStop(0.55, secondaryColor);
    bgGrad.addColorStop(1, primaryColor);
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // 2. Draw Decorative Ambient Radial Glow
    const radGlow1 = ctx.createRadialGradient(width * 0.8, height * 0.15, 10, width * 0.8, height * 0.15, width * 0.6);
    radGlow1.addColorStop(0, `${accentColor}35`);
    radGlow1.addColorStop(1, "transparent");
    ctx.fillStyle = radGlow1;
    ctx.fillRect(0, 0, width, height);

    const radGlow2 = ctx.createRadialGradient(width * 0.15, height * 0.85, 10, width * 0.15, height * 0.85, width * 0.5);
    radGlow2.addColorStop(0, `${primaryColor === "#070b19" ? "#8b5cf6" : accentColor}28`);
    radGlow2.addColorStop(1, "transparent");
    ctx.fillStyle = radGlow2;
    ctx.fillRect(0, 0, width, height);

    // 3. Optional Custom Uploaded Background Image
    if (customBgImage) {
      try {
        const bgImg = new Image();
        bgImg.src = customBgImage;
        if (bgImg.complete) {
          ctx.save();
          ctx.globalAlpha = 0.22;
          ctx.drawImage(bgImg, 0, 0, width, height);
          ctx.restore();
        }
      } catch (e) {}
    }

    // 4. Draw Graphic Theme Patterns
    const tmpl = TEMPLATES.find((t) => t.id === selectedTemplateId) || TEMPLATES[0];
    if (tmpl.pattern === "cyber") {
      // Tech Grid
      ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
      ctx.lineWidth = 1.5;
      const gridSize = 45;
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      // Glowing cyber circuits
      ctx.strokeStyle = `${accentColor}40`;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(width * 0.7, 0);
      ctx.lineTo(width * 0.7, height * 0.25);
      ctx.lineTo(width * 0.95, height * 0.25);
      ctx.stroke();
    } else if (tmpl.pattern === "neon_waves") {
      // Fluid waves
      ctx.strokeStyle = `${accentColor}30`;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.bezierCurveTo(0, height * 0.3, width * 0.5, height * 0.1, width, height * 0.4);
      ctx.stroke();
      ctx.beginPath();
      ctx.bezierCurveTo(0, height * 0.7, width * 0.6, height * 0.9, width, height * 0.6);
      ctx.stroke();
    } else if (tmpl.pattern === "kinetic_chevrons") {
      // Bold angular stripes
      ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
      ctx.lineWidth = 24;
      for (let i = -width; i < width * 2; i += 180) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i + height * 0.6, height);
        ctx.stroke();
      }
    } else if (tmpl.pattern === "minimal_circles") {
      // Elegant concentric rings
      ctx.strokeStyle = `${accentColor}25`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(width * 0.85, height * 0.2, 180, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(width * 0.85, height * 0.2, 260, 0, Math.PI * 2);
      ctx.stroke();
    }

    // 5. Decorative Frame Border
    ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
    ctx.lineWidth = 1.5;
    const margin = 28;
    ctx.strokeRect(margin, margin, width - margin * 2, height - margin * 2);

    // Corner Accents
    const cornerSize = 24;
    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 4;
    // Top-Left
    ctx.beginPath();
    ctx.moveTo(margin, margin + cornerSize);
    ctx.lineTo(margin, margin);
    ctx.lineTo(margin + cornerSize, margin);
    ctx.stroke();
    // Top-Right
    ctx.beginPath();
    ctx.moveTo(width - margin - cornerSize, margin);
    ctx.lineTo(width - margin, margin);
    ctx.lineTo(width - margin, margin + cornerSize);
    ctx.stroke();
    // Bottom-Left
    ctx.beginPath();
    ctx.moveTo(margin, height - margin - cornerSize);
    ctx.lineTo(margin, height - margin);
    ctx.lineTo(margin + cornerSize, height - margin);
    ctx.stroke();
    // Bottom-Right
    ctx.beginPath();
    ctx.moveTo(width - margin - cornerSize, height - margin);
    ctx.lineTo(width - margin, height - margin);
    ctx.lineTo(width - margin, height - margin - cornerSize);
    ctx.stroke();

    // 6. Draw EventSphere Verification Branding (Top Right)
    if (showBranding) {
      ctx.save();
      const brandX = width - margin - 32;
      const brandY = margin + 44;
      ctx.textAlign = "right";
      ctx.font = "bold 18px 'Outfit', sans-serif";
      ctx.fillStyle = textColor;
      ctx.fillText("EventSphere", brandX, brandY);

      ctx.font = "600 12px 'Inter', sans-serif";
      ctx.fillStyle = accentColor;
      ctx.fillText("OFFICIAL CAMPUS EVENT", brandX, brandY + 18);
      ctx.restore();
    }

    // 7. Top Category / Badge Pill
    const displayBadge = (badgeText || tmpl.badgeText || "CAMPUS EVENT").toUpperCase();
    ctx.save();
    const pillX = align === "center" ? width / 2 : margin + 48;
    const pillY = margin + 50;

    ctx.font = "bold 13px 'Plus Jakarta Sans', sans-serif";
    const pillTextWidth = ctx.measureText(displayBadge).width;
    const pillW = pillTextWidth + 36;
    const pillH = 34;
    const pillLeft = align === "center" ? pillX - pillW / 2 : pillX;

    // Pill background with glass effect
    ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
    ctx.beginPath();
    ctx.roundRect(pillLeft, pillY - pillH / 2, pillW, pillH, 17);
    ctx.fill();

    ctx.strokeStyle = `${accentColor}70`;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = accentColor;
    ctx.fillText(displayBadge, pillLeft + pillW / 2, pillY);
    ctx.restore();

    // 8. Event Headline / Title (with auto text-wrap and high-contrast glow)
    const displayTitle = (headline || eventForm.title || "ANNUAL CAMPUS EVENT").toUpperCase();
    ctx.save();
    const titleY = aspectRatio === "flyer" ? height * 0.32 : height * 0.36;
    const titleMaxWidth = width - margin * 2 - 120;

    // Title Font Size calculation
    let titleFontSize = aspectRatio === "flyer" ? 64 : 56;
    if (displayTitle.length > 35) titleFontSize = 46;
    if (displayTitle.length > 55) titleFontSize = 38;
    ctx.font = `900 ${titleFontSize}px 'Outfit', sans-serif`;
    ctx.textAlign = align === "center" ? "center" : "left";
    ctx.textBaseline = "top";

    // Text Shadow
    ctx.shadowColor = "rgba(0, 0, 0, 0.85)";
    ctx.shadowBlur = 24;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 4;
    ctx.fillStyle = textColor;

    // Auto Wrap Lines
    const words = displayTitle.split(" ");
    let line = "";
    const lines = [];
    for (let n = 0; n < words.length; n++) {
      const testLine = line + words[n] + " ";
      const metrics = ctx.measureText(testLine);
      if (metrics.width > titleMaxWidth && n > 0) {
        lines.push(line.trim());
        line = words[n] + " ";
      } else {
        line = testLine;
      }
    }
    lines.push(line.trim());

    const titleLineHeight = titleFontSize * 1.15;
    const titleStartX = align === "center" ? width / 2 : margin + 48;
    lines.forEach((l, idx) => {
      ctx.fillText(l, titleStartX, titleY + idx * titleLineHeight);
    });
    ctx.restore();

    // 9. Subtitle / Description
    const displaySub = subtitle || eventForm.description || "Join us for an inspiring campus experience with top coordinators.";
    const subStartY = titleY + lines.length * titleLineHeight + 16;
    ctx.save();
    ctx.font = "500 20px 'Inter', sans-serif";
    ctx.fillStyle = "rgba(241, 245, 249, 0.82)";
    ctx.textAlign = align === "center" ? "center" : "left";
    ctx.textBaseline = "top";

    // Wrap Subtitle
    const subWords = displaySub.split(" ");
    let subLine = "";
    const subLines = [];
    const subMaxWidth = width - margin * 2 - 160;
    for (let n = 0; n < subWords.length && subLines.length < 3; n++) {
      const testLine = subLine + subWords[n] + " ";
      if (ctx.measureText(testLine).width > subMaxWidth && n > 0) {
        subLines.push(subLine.trim());
        subLine = subWords[n] + " ";
      } else {
        subLine = testLine;
      }
    }
    if (subLine.trim() && subLines.length < 3) subLines.push(subLine.trim());

    subLines.forEach((l, idx) => {
      ctx.fillText(l, titleStartX, subStartY + idx * 28);
    });
    ctx.restore();

    // 10. Event Details Bar (Date, Time, Venue, Seats)
    const dateStr = eventForm.event_date ? String(eventForm.event_date) : "Scheduled Date";
    const timeStr = eventForm.event_time ? String(eventForm.event_time) : "9:00 AM";
    const venueStr = eventForm.venue ? String(eventForm.venue) : "Main Campus Auditorium";
    const organizer = organizerText || eventForm.organizer_name || "EventSphere Organizing Committee";

    const barW = width - margin * 2 - 96;
    const barH = 92;
    const barX = margin + 48;
    const barY = height - margin - barH - 44;

    ctx.save();
    // Glass bar background
    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
    ctx.beginPath();
    ctx.roundRect(barX, barY, barW, barH, 18);
    ctx.fill();

    ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Details Grid Columns (Date | Time | Venue | Host)
    const colW = barW / 3;

    // Col 1: DATE & TIME
    ctx.textAlign = "left";
    ctx.font = "bold 12px 'Inter', sans-serif";
    ctx.fillStyle = accentColor;
    ctx.fillText("DATE & TIME", barX + 28, barY + 28);

    ctx.font = "bold 16px 'Outfit', sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(`${dateStr} · ${timeStr}`, barX + 28, barY + 56);

    // Divider 1
    ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
    ctx.beginPath();
    ctx.moveTo(barX + colW, barY + 16);
    ctx.lineTo(barX + colW, barY + barH - 16);
    ctx.stroke();

    // Col 2: VENUE
    ctx.font = "bold 12px 'Inter', sans-serif";
    ctx.fillStyle = accentColor;
    ctx.fillText("VENUE", barX + colW + 28, barY + 28);

    ctx.font = "bold 16px 'Outfit', sans-serif";
    ctx.fillStyle = "#ffffff";
    const truncatedVenue = venueStr.length > 28 ? venueStr.slice(0, 26) + "..." : venueStr;
    ctx.fillText(truncatedVenue, barX + colW + 28, barY + 56);

    // Divider 2
    ctx.beginPath();
    ctx.moveTo(barX + colW * 2, barY + 16);
    ctx.lineTo(barX + colW * 2, barY + barH - 16);
    ctx.stroke();

    // Col 3: HOST / ORGANIZER
    ctx.font = "bold 12px 'Inter', sans-serif";
    ctx.fillStyle = accentColor;
    ctx.fillText("ORGANIZED BY", barX + colW * 2 + 28, barY + 28);

    ctx.font = "bold 15px 'Outfit', sans-serif";
    ctx.fillStyle = "#ffffff";
    const truncatedHost = organizer.length > 26 ? organizer.slice(0, 24) + "..." : organizer;
    ctx.fillText(truncatedHost, barX + colW * 2 + 28, barY + 56);

    ctx.restore();

    // 11. Footer verified stamp
    ctx.save();
    ctx.font = "500 12px 'Inter', sans-serif";
    ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
    ctx.textAlign = "center";
    ctx.fillText("EventSphere Campus Portal · Register online for attendance & certificates", width / 2, height - margin - 14);
    ctx.restore();
  }, [
    aspectRatio,
    selectedTemplateId,
    headline,
    subtitle,
    badgeText,
    organizerText,
    primaryColor,
    secondaryColor,
    accentColor,
    textColor,
    showBranding,
    align,
    customBgImage,
    customLogo,
    eventForm,
  ]);

  // Redraw canvas whenever parameters change
  useEffect(() => {
    drawPoster();
  }, [drawPoster]);

  // Export as PNG File and attach directly to event creation form
  const handleApplyAsCover = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    setExporting(true);
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          toast.error("Failed to generate image blob");
          setExporting(false);
          return;
        }

        const safeTitle = (headline || eventForm.title || "event")
          .toLowerCase()
          .replace(/[^a-z0-9]/g, "_")
          .slice(0, 28);
        const fileName = `${safeTitle}_poster.png`;
        const file = new File([blob], fileName, { type: "image/png" });
        const dataUrl = canvas.toDataURL("image/png");

        if (onApplyPoster) {
          onApplyPoster(file, dataUrl);
          setApplied(true);
          toast.success("Poster set as Event Cover Image!");
        }
        setExporting(false);
      },
      "image/png",
      0.96
    );
  };

  // Download high-resolution PNG
  const handleDownloadPng = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const safeTitle = (headline || eventForm.title || "event_poster")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "_")
      .slice(0, 32);

    const link = document.createElement("a");
    link.download = `${safeTitle}_poster.png`;
    link.href = canvas.toDataURL("image/png", 1.0);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Poster PNG downloaded successfully!");
  };

  // Download high-resolution PDF
  const handleDownloadPdf = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    try {
      const dataUrl = canvas.toDataURL("image/png", 1.0);
      const isFlyer = aspectRatio === "flyer";
      const orientation = isFlyer ? "portrait" : "landscape";
      const doc = new jsPDF({
        orientation,
        unit: "mm",
        format: "a4",
      });

      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      doc.addImage(dataUrl, "PNG", 0, 0, pageWidth, pageHeight);

      const safeTitle = (headline || eventForm.title || "event_poster")
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "_")
        .slice(0, 32);
      doc.save(`${safeTitle}_poster.pdf`);
      toast.success("Poster PDF downloaded successfully!");
    } catch (err) {
      console.error("PDF download failed:", err);
      toast.error("Could not export PDF.");
    }
  };

  // Upload Custom Background Image Handler
  const handleCustomBgUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) {
      toast.error("Background image exceeds 8MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = (evt) => {
      setCustomBgImage(evt.target.result);
      toast.success("Custom background loaded");
    };
    reader.readAsDataURL(file);
  };

  return (
    <div
      className="glass-card"
      style={{
        padding: "24px",
        borderRadius: "20px",
        marginTop: "24px",
        marginBottom: "24px",
        border: "1.5px solid rgba(139, 92, 246, 0.35)",
        background: "var(--bg-elevated)",
        boxShadow: "0 18px 45px rgba(0,0,0,0.35)",
      }}
    >
      {/* Header with Auto-Generate Action */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 14,
          marginBottom: 20,
          paddingBottom: 16,
          borderBottom: "1px solid var(--border-color)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 12,
                background: "var(--gradient-primary)",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 4px 14px rgba(139, 92, 246, 0.4)",
              }}
            >
              <HiSparkles size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
                Event Poster Designer
              </h3>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
                Generate high-resolution event posters tailored to your category or customize every detail.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => selectTemplateForCategory(eventForm.category || "Technical")}
            title="Auto-picks optimal template and colors based on event category"
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <FiRefreshCw size={14} /> Auto-Generate for Category
          </button>

          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handleApplyAsCover}
            disabled={exporting}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            {applied ? <FiCheck size={15} /> : <FiImage size={15} />}
            {applied ? "Cover Attached!" : "Use as Event Cover"}
          </button>
        </div>
      </div>

      {/* Main Split Interface: Left Controls / Right Live Canvas */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 24,
          alignItems: "start",
        }}
      >
        {/* LEFT COLUMN: DESIGN CONTROLS */}
        <div>
          {/* Subtabs for Easy Navigation */}
          <div
            style={{
              display: "flex",
              background: "var(--bg-base)",
              borderRadius: 12,
              padding: 4,
              marginBottom: 16,
              border: "1px solid var(--border-color)",
              gap: 4,
            }}
          >
            {[
              { id: "templates", label: "Templates" },
              { id: "content", label: "Typography" },
              { id: "colors", label: "Colors & Style" },
              { id: "assets", label: "Media & Badges" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className="btn btn-sm"
                style={{
                  flex: 1,
                  background: activeTab === tab.id ? "var(--gradient-primary)" : "transparent",
                  color: activeTab === tab.id ? "#ffffff" : "var(--text-secondary)",
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "6px 4px",
                  transition: "all 0.2s ease",
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* TAB 1: TEMPLATES */}
          {activeTab === "templates" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <label className="form-label" style={{ fontSize: 13, marginBottom: 4 }}>
                Select Thematic Preset
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {TEMPLATES.map((tmpl) => (
                  <button
                    key={tmpl.id}
                    type="button"
                    onClick={() => handleApplyTemplate(tmpl)}
                    style={{
                      padding: "12px",
                      borderRadius: "14px",
                      background:
                        selectedTemplateId === tmpl.id
                          ? "rgba(139, 92, 246, 0.16)"
                          : "var(--bg-base)",
                      border:
                        selectedTemplateId === tmpl.id
                          ? "1.5px solid #8b5cf6"
                          : "1px solid var(--border-color)",
                      textAlign: "left",
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                    }}
                  >
                    <div
                      style={{
                        height: 28,
                        borderRadius: 8,
                        background: `linear-gradient(135deg, ${tmpl.bgPrimary}, ${tmpl.bgSecondary})`,
                        border: `1px solid ${tmpl.accentColor}50`,
                        marginBottom: 8,
                      }}
                    />
                    <div style={{ fontWeight: 700, fontSize: 13, color: "var(--text-primary)" }}>
                      {tmpl.name}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                      {tmpl.category} Events
                    </div>
                  </button>
                ))}
              </div>

              {/* Aspect Ratio Switch */}
              <div style={{ marginTop: 14 }}>
                <label className="form-label" style={{ fontSize: 13 }}>
                  Canvas Aspect Ratio
                </label>
                <div style={{ display: "flex", gap: 10 }}>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setAspectRatio("banner")}
                    style={{
                      flex: 1,
                      background: aspectRatio === "banner" ? "var(--gradient-primary)" : "var(--bg-base)",
                      color: aspectRatio === "banner" ? "#fff" : "var(--text-secondary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: 10,
                      fontWeight: 600,
                    }}
                  >
                    16:9 Banner (Landscape)
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setAspectRatio("flyer")}
                    style={{
                      flex: 1,
                      background: aspectRatio === "flyer" ? "var(--gradient-primary)" : "var(--bg-base)",
                      color: aspectRatio === "flyer" ? "#fff" : "var(--text-secondary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: 10,
                      fontWeight: 600,
                    }}
                  >
                    4:5 Event Flyer (Portrait)
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CONTENT & TYPOGRAPHY */}
          {activeTab === "content" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Headline / Event Title</label>
                <input
                  className="form-input"
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  placeholder={eventForm.title || "ANNUAL HACKATHON"}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Badge Ribbon Tag</label>
                <input
                  className="form-input"
                  value={badgeText}
                  onChange={(e) => setBadgeText(e.target.value)}
                  placeholder="CAMPUS TECH SUMMIT"
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Description / Subtitle</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={subtitle}
                  onChange={(e) => setSubtitle(e.target.value)}
                  placeholder="Brief tagline or description for the poster..."
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Organizing Body / Department</label>
                <input
                  className="form-input"
                  value={organizerText}
                  onChange={(e) => setOrganizerText(e.target.value)}
                  placeholder={eventForm.organizer_name || "Department of Computer Science"}
                />
              </div>

              <div>
                <label className="form-label">Text Alignment</label>
                <div style={{ display: "flex", gap: 10 }}>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setAlign("center")}
                    style={{
                      flex: 1,
                      background: align === "center" ? "var(--gradient-primary)" : "var(--bg-base)",
                      color: align === "center" ? "#fff" : "var(--text-secondary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: 10,
                    }}
                  >
                    Centered
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setAlign("left")}
                    style={{
                      flex: 1,
                      background: align === "left" ? "var(--gradient-primary)" : "var(--bg-base)",
                      color: align === "left" ? "#fff" : "var(--text-secondary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: 10,
                    }}
                  >
                    Left Aligned
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: COLORS & STYLES */}
          {activeTab === "colors" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label className="form-label">Primary Color</label>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="color"
                      value={primaryColor}
                      onChange={(e) => setPrimaryColor(e.target.value)}
                      style={{ width: 44, height: 38, border: "none", cursor: "pointer", borderRadius: 8 }}
                    />
                    <input
                      className="form-input"
                      value={primaryColor}
                      onChange={(e) => setPrimaryColor(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="form-label">Secondary Color</label>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="color"
                      value={secondaryColor}
                      onChange={(e) => setSecondaryColor(e.target.value)}
                      style={{ width: 44, height: 38, border: "none", cursor: "pointer", borderRadius: 8 }}
                    />
                    <input
                      className="form-input"
                      value={secondaryColor}
                      onChange={(e) => setSecondaryColor(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label className="form-label">Accent Highlight</label>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="color"
                      value={accentColor}
                      onChange={(e) => setAccentColor(e.target.value)}
                      style={{ width: 44, height: 38, border: "none", cursor: "pointer", borderRadius: 8 }}
                    />
                    <input
                      className="form-input"
                      value={accentColor}
                      onChange={(e) => setAccentColor(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="form-label">Text Color</label>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="color"
                      value={textColor}
                      onChange={(e) => setTextColor(e.target.value)}
                      style={{ width: 44, height: 38, border: "none", cursor: "pointer", borderRadius: 8 }}
                    />
                    <input
                      className="form-input"
                      value={textColor}
                      onChange={(e) => setTextColor(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Quick Accent Palettes */}
              <div>
                <label className="form-label">Quick Accent Swatches</label>
                <div style={{ display: "flex", gap: 8 }}>
                  {["#06b6d4", "#8b5cf6", "#ec4899", "#f97316", "#10b981", "#fbbf24"].map((hex) => (
                    <button
                      key={hex}
                      type="button"
                      onClick={() => setAccentColor(hex)}
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: "50%",
                        background: hex,
                        border: accentColor === hex ? "2.5px solid #fff" : "none",
                        cursor: "pointer",
                        boxShadow: "0 2px 6px rgba(0,0,0,0.3)",
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: ASSETS & MEDIA */}
          {activeTab === "assets" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label className="form-label">Upload Background Image (Optional Overlay)</label>
                <label
                  className="btn btn-outline"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    cursor: "pointer",
                    width: "100%",
                  }}
                >
                  <FiUpload /> Choose Custom Background
                  <input type="file" accept="image/*" onChange={handleCustomBgUpload} style={{ display: "none" }} />
                </label>
                {customBgImage && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
                    <span style={{ fontSize: 12, color: "var(--success)" }}>✓ Background image loaded</span>
                    <button
                      type="button"
                      onClick={() => setCustomBgImage(null)}
                      style={{ background: "none", border: "none", color: "var(--danger)", fontSize: 12, cursor: "pointer" }}
                    >
                      Remove
                    </button>
                  </div>
                )}
              </div>

              {/* EventSphere Official Seal Toggle */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 14px",
                  borderRadius: 12,
                  background: "var(--bg-base)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>EventSphere Official Seal</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    Renders the verified campus event certification stamp
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={showBranding}
                  onChange={(e) => setShowBranding(e.target.checked)}
                  style={{ width: 18, height: 18, cursor: "pointer", accentColor: "#8b5cf6" }}
                />
              </div>
            </div>
          )}

          {/* Export Action Buttons */}
          <div
            style={{
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              marginTop: 20,
              paddingTop: 16,
              borderTop: "1px solid var(--border-color)",
            }}
          >
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={handleDownloadPng}
              style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
            >
              <FiDownload size={14} /> Download PNG
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={handleDownloadPdf}
              style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
            >
              <FiFileText size={14} /> Export PDF
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN: LIVE CANVAS PREVIEW */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          <div
            style={{
              width: "100%",
              maxWidth: "520px",
              borderRadius: "16px",
              overflow: "hidden",
              border: "1.5px solid rgba(139, 92, 246, 0.4)",
              boxShadow: "0 18px 45px rgba(0, 0, 0, 0.5), 0 0 25px rgba(139, 92, 246, 0.2)",
              background: "#000",
              position: "relative",
            }}
          >
            <canvas
              ref={canvasRef}
              style={{
                width: "100%",
                height: "auto",
                display: "block",
              }}
            />
          </div>

          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 10, textAlign: "center" }}>
            Live High-Resolution Poster Canvas (Auto-scaled for preview · Exports at 2x Ultra-HD)
          </p>
        </div>
      </div>
    </div>
  );
}
