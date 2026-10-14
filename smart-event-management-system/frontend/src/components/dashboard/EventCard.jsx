import { motion } from "framer-motion";
import { FiCalendar, FiClock, FiMapPin, FiUsers, FiArrowRight } from "react-icons/fi";
import { Link, useLocation } from "react-router-dom";
import { formatDate } from "../../utils/format.js";
import EventImage from "../common/EventImage.jsx";

export default function EventCard({ event, actionSlot, index = 0 }) {
  const location = useLocation();
  const seatsLeft = event.available_seats;
  const isFull = seatsLeft <= 0;

  const detailPath = location.pathname.startsWith("/student")
    ? `/student/events/${event.id}`
    : location.pathname.startsWith("/faculty")
    ? `/faculty/events/${event.id}`
    : `/events/${event.id}`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      whileHover={{ y: -7, transition: { duration: 0.22, ease: "easeOut" } }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
      className="glass-card glass-card-interactive"
      style={{
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        borderRadius: "20px",
        position: "relative",
      }}
    >
      {/* Poster with hover zoom and graceful fallback */}
      <div
        style={{
          height: 175,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <EventImage
          src={event.poster_url}
          alt={event.title}
          category={event.category}
          hoverZoom
        />

        {/* Category Badge */}
        <span
          className="badge"
          style={{
            position: "absolute",
            top: 14,
            left: 14,
            background: "rgba(15, 23, 42, 0.7)",
            color: "#ffffff",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            fontSize: "12px",
            fontWeight: 600,
            padding: "4px 12px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          }}
        >
          {event.category || "General"}
        </span>
      </div>

      {/* Content */}
      <div style={{ padding: "20px 20px 18px", display: "flex", flexDirection: "column", gap: 12, flex: 1 }}>
        <h3
          style={{
            fontSize: 17,
            lineHeight: 1.35,
            fontWeight: 700,
            color: "var(--text-primary)",
          }}
        >
          {event.title}
        </h3>

        <p
          style={{
            fontSize: 13.5,
            color: "var(--text-secondary)",
            lineHeight: 1.5,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {event.description}
        </p>

        {/* Meta Info Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "8px 12px",
            fontSize: 13,
            color: "var(--text-secondary)",
            margin: "4px 0",
            padding: "10px 12px",
            background: "var(--bg-elevated)",
            borderRadius: "12px",
            border: "1px solid var(--border-color)",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            <FiCalendar size={14} style={{ color: "#8b5cf6", flexShrink: 0 }} />
            {formatDate(event.event_date)}
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            <FiClock size={14} style={{ color: "#8b5cf6", flexShrink: 0 }} />
            {event.event_time}
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            <FiMapPin size={14} style={{ color: "#8b5cf6", flexShrink: 0 }} />
            {event.venue}
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 7, fontWeight: 600, color: isFull ? "var(--danger)" : "var(--success)" }}>
            <FiUsers size={14} style={{ flexShrink: 0 }} />
            {isFull ? "Full" : `${seatsLeft} seats`}
          </span>
        </div>

        {/* Card Action */}
        <div style={{ marginTop: "auto", display: "flex", gap: 10, paddingTop: 6 }}>
          <Link
            to={detailPath}
            className="btn btn-outline btn-sm"
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "9px 16px",
            }}
          >
            <span>View Details</span>
            <FiArrowRight size={13} />
          </Link>
          {actionSlot}
        </div>
      </div>
    </motion.div>
  );
}
