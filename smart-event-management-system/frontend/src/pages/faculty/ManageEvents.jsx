import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import {
  FiPlus,
  FiEdit2,
  FiTrash2,
  FiUsers,
  FiUpload,
  FiClock,
  FiUser,
  FiInfo,
  FiGrid,
  FiSearch,
  FiImage,
  FiFileText,
} from "react-icons/fi";
import { HiSparkles } from "react-icons/hi";
import Modal from "../../components/ui/Modal.jsx";
import EmptyState from "../../components/ui/EmptyState.jsx";
import Pagination from "../../components/ui/Pagination.jsx";
import { SkeletonGrid } from "../../components/ui/Loader.jsx";
import EventImage from "../../components/common/EventImage.jsx";
import EventPosterDesigner from "../../components/events/EventPosterDesigner.jsx";
import { eventService } from "../../api/services.js";
import { fileUrl, formatDate } from "../../utils/format.js";

const categories = ["Technical", "Cultural", "Sports", "Workshop", "Seminar", "Hackathon", "Other"];

const emptyForm = {
  title: "",
  description: "",
  category: "Technical",
  venue: "",
  event_date: "",
  event_time: "",
  total_seats: 50,
  registration_type: "both",
  max_team_size: 4,
  rules: "",
  requirements: "",
};

export default function ManageEvents() {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [modalTab, setModalTab] = useState("info");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [posterFile, setPosterFile] = useState(null);
  const [posterPreview, setPosterPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  // Edit History Modal State
  const [historyModalTarget, setHistoryModalTarget] = useState(null);
  const [historyList, setHistoryList] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const load = () => {
    setLoading(true);
    eventService
      .list({ page, page_size: 9, sort_by: "created_at", sort_order: "desc" })
      .then(({ data }) => {
        setEvents(data.items);
        setTotal(data.total);
      })
      .catch(() => toast.error("Could not load events"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [page]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setPosterFile(null);
    setPosterPreview(null);
    setModalTab("info");
    setModalOpen(true);
  };

  const openEdit = (ev) => {
    setEditing(ev);
    setForm({
      title: ev.title || "",
      description: ev.description || "",
      category: ev.category || "Technical",
      venue: ev.venue || "",
      event_date: ev.event_date || "",
      event_time: ev.event_time || "",
      total_seats: ev.total_seats || 50,
      registration_type: ev.registration_type || "both",
      max_team_size: ev.max_team_size || 4,
      rules: ev.rules || "",
      requirements: ev.requirements || "",
    });
    setPosterFile(null);
    setPosterPreview(ev.poster_url ? fileUrl(ev.poster_url) : null);
    setModalTab("info");
    setModalOpen(true);
  };

  const openHistory = async (ev) => {
    setHistoryModalTarget(ev);
    setHistoryLoading(true);
    try {
      const { data } = await eventService.history(ev.id);
      setHistoryList(data);
    } catch {
      toast.error("Could not fetch edit history for this event");
      setHistoryList([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handlePoster = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPosterFile(file);
    setPosterPreview(URL.createObjectURL(file));
  };

  const update = (field) => (e) => {
    const val = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [field]: val }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const fd = new FormData();
    fd.append("title", form.title);
    fd.append("description", form.description);
    fd.append("category", form.category);
    fd.append("venue", form.venue);
    fd.append("event_date", form.event_date);
    fd.append("event_time", form.event_time);
    fd.append("total_seats", form.total_seats);
    fd.append("registration_type", form.registration_type);
    if (form.registration_type !== "individual") {
      fd.append("max_team_size", form.max_team_size);
    }
    if (form.rules) fd.append("rules", form.rules);
    if (form.requirements) fd.append("requirements", form.requirements);
    if (posterFile) fd.append("poster", posterFile);

    try {
      if (editing) {
        await eventService.update(editing.id, fd);
        toast.success("Event updated successfully");
      } else {
        await eventService.create(fd);
        toast.success("Event created successfully");
      }
      setModalOpen(false);
      load();
    } catch (err) {
      console.error("Save event error:", err);
      let msg = "Could not save event";
      const detail = err.response?.data?.detail || err.response?.data?.message;
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail)) {
        msg = detail.map((d) => (typeof d === "string" ? d : d.message || d.msg || JSON.stringify(d))).join(", ");
      }
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await eventService.remove(deleteTarget.id);
      toast.success("Event deleted");
      setDeleteTarget(null);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not delete event");
    }
  };

  const filteredEvents = events.filter((ev) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase().trim();
    return (
      (ev.title && ev.title.toLowerCase().includes(q)) ||
      (ev.category && ev.category.toLowerCase().includes(q)) ||
      (ev.venue && ev.venue.toLowerCase().includes(q)) ||
      (ev.organizer_name && ev.organizer_name.toLowerCase().includes(q)) ||
      (ev.registration_type && ev.registration_type.toLowerCase().includes(q))
    );
  });

  return (
    <div>
      <div className="section-head">
        <div>
          <h1 className="page-title">Manage Events</h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            Create, edit, manage registrations, and collaborate on campus events across faculty organizers.
          </p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={openCreate}>
          <FiPlus /> Add Event
        </button>
      </div>

      {/* Search Bar */}
      <div className="glass-card" style={{ padding: "14px 18px", marginBottom: 20 }}>
        <div style={{ position: "relative", maxWidth: 460 }}>
          <FiSearch style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input
            className="form-input"
            style={{ paddingLeft: 40, paddingRight: search ? 36 : 14, borderRadius: 10 }}
            placeholder="Search by event title, category, venue, or organizer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              style={{
                position: "absolute",
                right: 12,
                top: "50%",
                transform: "translateY(-50%)",
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                padding: "2px 6px",
                fontSize: 14,
                borderRadius: "50%",
              }}
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <SkeletonGrid count={6} />
      ) : events.length === 0 ? (
        <EmptyState
          title="No events yet"
          message="Create your first event to get started."
          action={
            <button className="btn btn-primary btn-sm" onClick={openCreate}>
              Add Event
            </button>
          }
        />
      ) : filteredEvents.length === 0 ? (
        <EmptyState
          title="No matching events"
          message={`No events match "${search}". Try a different search term.`}
          action={
            <button className="btn btn-secondary btn-sm" onClick={() => setSearch("")}>
              Clear Search
            </button>
          }
        />
      ) : (
        <>
          <div className="grid-cards">
            {filteredEvents.map((ev) => (
              <div key={ev.id} className="glass-card" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
                <div style={{ height: 140, overflow: "hidden", position: "relative" }}>
                  <EventImage
                    src={ev.poster_url}
                    alt={ev.title}
                    category={ev.category}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                </div>
                <div style={{ padding: 18, flex: 1, display: "flex", flexDirection: "column" }}>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                    <span className="badge badge-info">{ev.category}</span>
                    <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>
                      {ev.registration_type || "Both"}
                    </span>
                  </div>

                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>{ev.title}</h3>
                  <p style={{ fontSize: 12.5, color: "var(--text-muted)", marginBottom: 8 }}>
                    {formatDate(ev.event_date)} · {ev.available_seats} spots available
                  </p>

                  {/* Creator / Updater Attribution */}
                  <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginBottom: 14, background: "var(--bg-base)", padding: "6px 10px", borderRadius: 8 }}>
                    <div>Organizer: <strong style={{ color: "var(--text-primary)" }}>{ev.organizer_name || "Faculty"}</strong></div>
                    {ev.updated_by_name && (
                      <div style={{ marginTop: 2, color: "#8b5cf6" }}>
                        Last edited by {ev.updated_by_name}
                      </div>
                    )}
                  </div>

                  <div style={{ marginTop: "auto", display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <button className="btn btn-outline btn-sm" style={{ flex: 1 }} onClick={() => openEdit(ev)}>
                      <FiEdit2 size={13} /> Edit
                    </button>
                    <button className="btn btn-outline btn-sm" title="View Edit History" onClick={() => openHistory(ev)}>
                      <FiClock size={13} /> History
                    </button>
                    <Link to="/faculty/registrations" state={{ eventId: ev.id }} className="btn btn-outline btn-sm">
                      <FiUsers size={13} /> Regs
                    </Link>
                    <button
                      className="btn btn-sm"
                      style={{ background: "rgba(220,38,38,0.1)", color: "var(--danger)" }}
                      onClick={() => setDeleteTarget(ev)}
                    >
                      <FiTrash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Pagination page={page} pageSize={9} total={total} onPageChange={setPage} />
        </>
      )}

      {/* CREATE / EDIT EVENT MODAL */}
      <Modal open={modalOpen} onClose={() => !saving && setModalOpen(false)} title={editing ? "Edit Event" : "Create New Event"} width={840}>
        {/* Navigation Tabs between Form & AI Poster Designer */}
        <div
          style={{
            display: "flex",
            gap: 8,
            marginBottom: 20,
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            paddingBottom: 12,
            flexWrap: "wrap",
          }}
        >
          <button
            type="button"
            onClick={() => setModalTab("info")}
            className={`btn btn-sm ${modalTab === "info" ? "btn-primary" : "btn-secondary"}`}
            style={{ display: "flex", alignItems: "center", gap: 7 }}
          >
            <FiFileText size={14} /> 1. Event Details
          </button>
          <button
            type="button"
            onClick={() => setModalTab("designer")}
            className={`btn btn-sm ${modalTab === "designer" ? "btn-primary" : "btn-secondary"}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              background:
                modalTab === "designer"
                  ? "linear-gradient(135deg, #8b5cf6, #ec4899)"
                  : "rgba(139, 92, 246, 0.12)",
              color: modalTab === "designer" ? "#ffffff" : "#c084fc",
              borderColor: "rgba(139, 92, 246, 0.3)",
            }}
          >
            <HiSparkles size={14} /> 2. Event Poster Designer
            {posterPreview && (
              <span
                className="badge badge-success"
                style={{ fontSize: 10, padding: "2px 6px", marginLeft: 4 }}
              >
                Cover Ready
              </span>
            )}
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {/* TAB 1: EVENT DETAILS */}
          <div style={{ display: modalTab === "info" ? "block" : "none" }}>
            {/* Poster Header with Quick Launcher */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 16,
                padding: "14px 18px",
                background: "var(--bg-base)",
                borderRadius: 14,
                border: "1px dashed var(--border-color)",
                marginBottom: 20,
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div
                  style={{
                    width: 90,
                    height: 60,
                    borderRadius: 10,
                    overflow: "hidden",
                    border: "1px solid var(--border-color)",
                    background: "var(--gradient-soft)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {posterPreview ? (
                    <img
                      src={posterPreview}
                      alt="Cover preview"
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  ) : (
                    <span style={{ fontSize: 11, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                      <FiImage size={14} /> No Cover
                    </span>
                  )}
                </div>
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--text-primary)" }}>
                    {posterPreview ? "Event Cover Image Selected" : "Event Cover & Poster"}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
                    Upload your own image or design an AI-style flyer poster
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <label className="btn btn-secondary btn-sm" style={{ cursor: "pointer", margin: 0, display: "flex", alignItems: "center", gap: 6 }}>
                  <FiUpload size={13} /> Upload File
                  <input type="file" accept="image/*" style={{ display: "none" }} onChange={handlePoster} />
                </label>
                <button
                  type="button"
                  onClick={() => setModalTab("designer")}
                  className="btn btn-sm"
                  style={{
                    background: "linear-gradient(135deg, rgba(139,92,246,0.25), rgba(236,72,153,0.25))",
                    borderColor: "rgba(139,92,246,0.5)",
                    color: "#c084fc",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontWeight: 600,
                  }}
                >
                  <HiSparkles size={13} /> {posterPreview ? "Edit in Studio" : "Open Poster Designer"}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Event Title</label>
              <input className="form-input" value={form.title} onChange={update("title")} required placeholder="e.g. Annual Hackathon 2026" />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div className="form-group">
                <label className="form-label">Category</label>
                <select className="form-select" value={form.category} onChange={update("category")}>
                  {categories.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Venue</label>
                <input className="form-input" value={form.venue} onChange={update("venue")} required placeholder="Auditorium / Lab 3" />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="form-textarea" rows={3} value={form.description} onChange={update("description")} required />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Event Date</label>
                <input type="date" className="form-input" value={form.event_date} onChange={update("event_date")} required />
              </div>
              <div className="form-group">
                <label className="form-label">Time</label>
                <input type="time" className="form-input" value={form.event_time} onChange={update("event_time")} required />
              </div>
              <div className="form-group">
                <label className="form-label">Capacity (Seats)</label>
                <input type="number" min={1} className="form-input" value={form.total_seats} onChange={update("total_seats")} required />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Registration Type</label>
              <select className="form-select" value={form.registration_type} onChange={update("registration_type")}>
                <option value="both">Both (Individual & Team)</option>
                <option value="individual">Individual Only</option>
                <option value="team">Team Only</option>
              </select>
            </div>

            {form.registration_type !== "individual" && (
              <div className="form-group">
                <label className="form-label">Max Team Size</label>
                <input
                  type="number"
                  min={2}
                  max={20}
                  className="form-input"
                  value={form.max_team_size}
                  onChange={update("max_team_size")}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Rules & Guidelines (Optional)</label>
              <textarea
                className="form-textarea"
                rows={2}
                value={form.rules}
                onChange={update("rules")}
                placeholder="e.g. 1. Bring college ID card. 2. Laptops required for coding rounds."
              />
            </div>

            <div className="form-group">
              <label className="form-label">Requirements & Eligibility (Optional)</label>
              <textarea
                className="form-textarea"
                rows={2}
                value={form.requirements}
                onChange={update("requirements")}
                placeholder="e.g. Open to all 2nd and 3rd year engineering students."
              />
            </div>
          </div>

          {/* TAB 2: POSTER DESIGNER (Kept mounted to preserve state & canvas) */}
          <div style={{ display: modalTab === "designer" ? "block" : "none" }}>
            <EventPosterDesigner
              eventForm={form}
              onApplyPoster={(file, dataUrl) => {
                setPosterFile(file);
                setPosterPreview(dataUrl);
                setModalTab("info");
              }}
              existingPosterUrl={editing?.poster_url}
            />
          </div>

          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            {modalTab === "designer" && (
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setModalTab("info")}
              >
                Back to Details
              </button>
            )}
            <button className="btn btn-primary" style={{ flex: 1 }} disabled={saving}>
              {saving ? "Saving..." : editing ? "Save Changes" : "Create Event"}
            </button>
          </div>
        </form>
      </Modal>

      {/* EVENT EDIT HISTORY MODAL */}
      <Modal
        open={!!historyModalTarget}
        onClose={() => setHistoryModalTarget(null)}
        title={`Edit History: ${historyModalTarget?.title}`}
        width={560}
      >
        {historyLoading ? (
          <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted)" }}>Loading history...</div>
        ) : historyList.length === 0 ? (
          <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted)" }}>
            <FiInfo size={28} style={{ marginBottom: 8 }} />
            <p>No edits have been made to this event yet.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14, maxHeight: 400, overflowY: "auto" }}>
            {historyList.map((h) => (
              <div
                key={h.id}
                style={{
                  padding: 14,
                  borderRadius: 12,
                  background: "var(--bg-base)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <div style={{ fontWeight: 600, fontSize: 13.5, color: "#8b5cf6" }}>
                    {h.faculty_name} ({h.action.toUpperCase()})
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    {new Date(h.created_at).toLocaleString()}
                  </div>
                </div>

                <div style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
                  {Object.entries(h.changed_fields || {}).map(([field, val]) => (
                    <div key={field} style={{ marginTop: 3 }}>
                      <strong style={{ textTransform: "capitalize", color: "var(--text-primary)" }}>{field.replace("_", " ")}:</strong>{" "}
                      <span style={{ textDecoration: "line-through", color: "var(--text-muted)" }}>{String(val.old || "None")}</span>{" "}
                      &rarr; <span style={{ color: "var(--success)", fontWeight: 500 }}>{String(val.new || "None")}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* DELETE CONFIRMATION MODAL */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Event" width={380}>
        <p style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 20 }}>
          Are you sure you want to delete "{deleteTarget?.title}"? This cannot be undone.
        </p>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-outline" style={{ flex: 1 }} onClick={() => setDeleteTarget(null)}>
            Cancel
          </button>
          <button className="btn btn-danger" style={{ flex: 1 }} onClick={handleDelete}>
            Delete
          </button>
        </div>
      </Modal>

      <style>{`
        @media (max-width: 560px) {
          .glass-card form div[style*="1fr 1fr"] { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
