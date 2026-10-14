import { useState } from "react";
import { motion } from "framer-motion";
import {
  FiCalendar,
  FiCpu,
  FiActivity,
  FiMusic,
  FiAward,
  FiBookOpen,
  FiLayers,
} from "react-icons/fi";
import { fileUrl } from "../../utils/format.js";

// Curated themes and icons per event category for graceful, premium visual fallback
const categoryThemes = {
  technical: {
    gradient: "linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%)",
    accent: "#818cf8",
    icon: FiCpu,
    label: "Technical",
  },
  cultural: {
    gradient: "linear-gradient(135deg, #4a044e 0%, #701a75 50%, #a21caf 100%)",
    accent: "#f472b6",
    icon: FiMusic,
    label: "Cultural",
  },
  sports: {
    gradient: "linear-gradient(135deg, #451a03 0%, #78350f 50%, #b45309 100%)",
    accent: "#fbbf24",
    icon: FiActivity,
    label: "Sports",
  },
  academic: {
    gradient: "linear-gradient(135deg, #064e3b 0%, #065f46 50%, #047857 100%)",
    accent: "#34d399",
    icon: FiBookOpen,
    label: "Academic",
  },
  seminar: {
    gradient: "linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)",
    accent: "#38bdf8",
    icon: FiAward,
    label: "Seminar",
  },
  workshop: {
    gradient: "linear-gradient(135deg, #134e4a 0%, #115e59 50%, #0f766e 100%)",
    accent: "#2dd4bf",
    icon: FiLayers,
    label: "Workshop",
  },
  default: {
    gradient: "linear-gradient(135deg, #2e1065 0%, #4c1d95 50%, #6d28d9 100%)",
    accent: "#a78bfa",
    icon: FiCalendar,
    label: "Campus Event",
  },
};

function getTheme(category) {
  if (!category) return categoryThemes.default;
  const key = String(category).toLowerCase().trim();
  for (const [catKey, val] of Object.entries(categoryThemes)) {
    if (key.includes(catKey)) return val;
  }
  return categoryThemes.default;
}

export default function EventImage({
  src,
  alt = "Event Cover",
  category = "General",
  style = {},
  className = "",
  hoverZoom = false,
  aspectRatio = null,
}) {
  const [loaded, setLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);

  const cleanUrl = fileUrl(src);
  const theme = getTheme(category);
  const CategoryIcon = theme.icon;

  const showFallback = !cleanUrl || hasError;

  return (
    <div
      className={className}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        background: theme.gradient,
        aspectRatio: aspectRatio || undefined,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        ...style,
      }}
    >
      {/* Decorative ambient background mesh for fallback or loading */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 80% 20%, rgba(255,255,255,0.12) 0%, transparent 60%), radial-gradient(circle at 20% 80%, rgba(0,0,0,0.35) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      {/* Subtle geometric grid lines */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
          pointerEvents: "none",
        }}
      />

      {/* Loading Skeleton Shimmer */}
      {!showFallback && !loaded && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.03) 100%)",
            backgroundSize: "200% 100%",
            animation: "pulse 1.8s infinite ease-in-out",
            zIndex: 1,
          }}
        />
      )}

      {/* Actual Image */}
      {!showFallback && (
        <motion.img
          src={cleanUrl}
          alt={alt}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setHasError(true)}
          whileHover={hoverZoom ? { scale: 1.06 } : undefined}
          transition={{ duration: 0.35, ease: "easeOut" }}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: "block",
            opacity: loaded ? 1 : 0,
            transition: "opacity 0.25s ease-in-out",
            position: "relative",
            zIndex: 2,
          }}
        />
      )}

      {/* Fallback Display (When image is missing, loading failed, or genuinely unavailable) */}
      {showFallback && (
        <div
          style={{
            position: "relative",
            zIndex: 2,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            padding: "16px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: "16px",
              background: "rgba(255, 255, 255, 0.12)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              border: "1px solid rgba(255, 255, 255, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: theme.accent,
              boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
            }}
          >
            <CategoryIcon size={26} />
          </div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "#ffffff",
              letterSpacing: "0.4px",
              textTransform: "uppercase",
              opacity: 0.9,
              textShadow: "0 2px 4px rgba(0,0,0,0.4)",
            }}
          >
            {category || "EventSphere"}
          </div>
        </div>
      )}
    </div>
  );
}
