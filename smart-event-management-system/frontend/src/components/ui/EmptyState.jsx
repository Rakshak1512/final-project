import React from "react";
import { Link } from "react-router-dom";
import { FiInbox } from "react-icons/fi";

export default function EmptyState({ icon, title = "Nothing here yet", message = "", action = null }) {
  const renderAction = () => {
    if (!action) return null;
    if (React.isValidElement(action)) return action;
    if (typeof action === "object" && action.label) {
      if (action.href) {
        return (
          <Link to={action.href} className="btn btn-primary" style={{ marginTop: 8 }}>
            {action.label}
          </Link>
        );
      }
      if (action.onClick) {
        return (
          <button type="button" onClick={action.onClick} className="btn btn-primary" style={{ marginTop: 8 }}>
            {action.label}
          </button>
        );
      }
    }
    return null;
  };

  return (
    <div
      className="glass-card"
      style={{
        padding: "56px 24px",
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: "50%",
          background: "var(--gradient-soft)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#8b5cf6",
          fontSize: 28,
        }}
      >
        {icon || <FiInbox />}
      </div>
      <h3 style={{ fontSize: 17, fontWeight: 700 }}>{title}</h3>
      {message && <p style={{ color: "var(--text-secondary)", fontSize: 14, maxWidth: 360 }}>{message}</p>}
      {renderAction()}
    </div>
  );
}
