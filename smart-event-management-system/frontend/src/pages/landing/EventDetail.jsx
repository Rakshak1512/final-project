import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import {
  FiCalendar,
  FiClock,
  FiMapPin,
  FiUsers,
  FiArrowLeft,
  FiUser,
  FiMail,
  FiBookOpen,
  FiDownload,
  FiCheckCircle,
  FiPlus,
  FiTrash2,
  FiSearch,
  FiAlertCircle,
  FiFileText,
} from "react-icons/fi";
import PublicNavbar from "../../components/landing/PublicNavbar.jsx";
import PublicFooter from "../../components/landing/PublicFooter.jsx";
import { SkeletonCard } from "../../components/ui/Loader.jsx";
import Modal from "../../components/ui/Modal.jsx";
import { eventService, registrationService } from "../../api/services.js";
import { useAuth } from "../../context/AuthContext.jsx";
import { useRealtime } from "../../context/RealtimeContext.jsx";
import { fileUrl, formatDate } from "../../utils/format.js";
import EventImage from "../../components/common/EventImage.jsx";

export default function EventDetail({ embedded = false }) {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [registering, setRegistering] = useState(false);
  const [registration, setRegistration] = useState(null);
  const [myTeam, setMyTeam] = useState(null);
  const [qrModal, setQrModal] = useState(null);

  // Team Registration Modal State
  const [teamModalOpen, setTeamModalOpen] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [searchRegNo, setSearchRegNo] = useState("");
  const [searchingStudent, setSearchingStudent] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [teamMembers, setTeamMembers] = useState([]); // [{ registration_number, name, department, semester }]
  const [teamSubmitting, setTeamSubmitting] = useState(false);

  const { subscribeToEvent, addListener } = useRealtime();

  useEffect(() => {
    if (id) {
      subscribeToEvent(id);
    }
  }, [id, subscribeToEvent]);

  // Real-time capacity and registration synchronization
  useEffect(() => {
    if (!id) return;
    const remove = addListener((msg) => {
      if (!msg.event_id || String(msg.event_id) === String(id)) {
        eventService
          .get(id)
          .then(({ data }) => setEvent(data))
          .catch(() => {});
        if (user && user.role === "student") {
          registrationService
            .my()
            .then(({ data: myRegs }) => {
              const found = myRegs.find((r) => r.event_id === Number(id) && r.status !== "cancelled");
              if (found) setRegistration(found);
            })
            .catch(() => {});
        }
      }
    });
    return () => remove();
  }, [id, addListener, user]);

  useEffect(() => {
    setLoading(true);
    eventService
      .get(id)
      .then(({ data }) => {
        setEvent(data);
        if (user && user.role === "student") {
          registrationService
            .my()
            .then(({ data: myRegs }) => {
              const found = myRegs.find((r) => r.event_id === Number(id) && r.status !== "cancelled");
              if (found) {
                setRegistration(found);
                if (found.team_id) {
                  registrationService
                    .myTeams()
                    .then(({ data: teams }) => {
                      const t = teams.find((item) => item.id === found.team_id);
                      if (t) setMyTeam(t);
                    })
                    .catch(() => {});
                }
              }
            })
            .catch(() => {});
        }
      })
      .catch(() => toast.error("Event not found"))
      .finally(() => setLoading(false));
  }, [id, user]);

  const handleRegisterIndividual = async () => {
    if (!user) {
      navigate("/login");
      return;
    }
    if (user.role !== "student") {
      toast.error("Only students can register for events");
      return;
    }
    setRegistering(true);
    try {
      const { data: newReg } = await registrationService.register(event.id);
      toast.success("Registered! Your QR ticket is ready.");
      setRegistration(newReg);
      setQrModal(newReg);
      const { data: updated } = await eventService.get(id);
      setEvent(updated);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Registration failed");
    } finally {
      setRegistering(false);
    }
  };

  const openTeamModal = () => {
    if (!user) {
      navigate("/login");
      return;
    }
    if (user.role !== "student") {
      toast.error("Only students can register teams");
      return;
    }
    setTeamName("");
    setSearchRegNo("");
    setSearchError("");
    setTeamMembers([]);
    setTeamModalOpen(true);
  };

  const handleSearchAndAddMember = async (e) => {
    e?.preventDefault();
    const cleanReg = searchRegNo.trim().toUpperCase();
    if (!cleanReg) return;

    if (cleanReg === (user.registration_number || "").toUpperCase()) {
      setSearchError("You are already the Team Leader.");
      return;
    }

    if (teamMembers.some((m) => m.registration_number.toUpperCase() === cleanReg)) {
      setSearchError("This student has already been added to the team list.");
      return;
    }

    const maxAllowed = (event.max_team_size || 4) - 1; // excluding leader
    if (teamMembers.length >= maxAllowed) {
      setSearchError(`Team is full. Maximum team size is ${event.max_team_size || 4}.`);
      return;
    }

    setSearchingStudent(true);
    setSearchError("");
    try {
      const { data: student } = await registrationService.searchStudent(cleanReg, event.id);
      setTeamMembers((prev) => [...prev, student]);
      setSearchRegNo("");
      toast.success(`Added ${student.name} to team.`);
    } catch (err) {
      const detail = err.response?.data?.detail || "Failed to find student.";
      setSearchError(detail);
    } finally {
      setSearchingStudent(false);
    }
  };

  const handleRemoveMember = (regNo) => {
    setTeamMembers((prev) => prev.filter((m) => m.registration_number !== regNo));
  };

  const handleSubmitTeam = async (e) => {
    e.preventDefault();
    if (!teamName.trim()) {
      toast.error("Please enter a team name.");
      return;
    }
    setTeamSubmitting(true);
    try {
      const payload = {
        event_id: event.id,
        team_name: teamName.trim(),
        member_registration_numbers: teamMembers.map((m) => m.registration_number),
      };
      const { data: teamResult } = await registrationService.registerTeam(payload);
      toast.success(`Team "${teamResult.name}" successfully registered!`);
      setTeamModalOpen(false);

      // Refresh registration status
      const { data: myRegs } = await registrationService.my();
      const found = myRegs.find((r) => r.event_id === Number(id) && r.status !== "cancelled");
      if (found) {
        setRegistration(found);
        setQrModal(found);
        setMyTeam(teamResult);
      }
      const { data: updated } = await eventService.get(id);
      setEvent(updated);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Team registration failed.");
    } finally {
      setTeamSubmitting(false);
    }
  };

  const backLink = user?.role === "student" ? "/student/events" : user?.role === "faculty" ? "/faculty/events" : "/events";

  const content = (
    <>
      <Link
        to={backLink}
        className="btn btn-outline btn-sm"
        style={{ marginBottom: 24, width: "fit-content", display: "inline-flex", alignItems: "center", gap: 8 }}
      >
        <FiArrowLeft /> Back to events
      </Link>

      {loading ? (
        <SkeletonCard />
      ) : !event ? (
        <p>Event not found.</p>
      ) : (
        <div className="glass-card" style={{ overflow: "hidden" }}>
          <div style={{ height: 280, position: "relative", overflow: "hidden" }}>
            <EventImage
              src={event.poster_url}
              alt={event.title}
              category={event.category}
              style={{ height: "100%" }}
            />
          </div>

          <div style={{ padding: 32 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
              <span className="badge badge-info">{event.category}</span>
              {event.registration_type && (
                <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>
                  {event.registration_type === "both"
                    ? "Individual & Team"
                    : event.registration_type === "team"
                    ? `Team Only (Max ${event.max_team_size || 4})`
                    : "Individual Only"}
                </span>
              )}
            </div>

            <h1 style={{ fontSize: 28, marginBottom: 14 }}>{event.title}</h1>
            <p style={{ color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 26 }}>{event.description}</p>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 26 }}>
              <InfoBlock icon={<FiCalendar />} label="Date" value={formatDate(event.event_date)} />
              <InfoBlock icon={<FiClock />} label="Time" value={event.event_time} />
              <InfoBlock icon={<FiMapPin />} label="Venue" value={event.venue} />
              <InfoBlock icon={<FiUsers />} label="Capacity" value={`${event.available_seats} / ${event.total_seats}`} />
            </div>

            {/* RULES & REQUIREMENTS IF PROVIDED */}
            {(event.rules || event.requirements) && (
              <div
                style={{
                  marginBottom: 26,
                  padding: 20,
                  borderRadius: 14,
                  background: "var(--bg-base)",
                  border: "1px solid var(--border-color)",
                }}
              >
                {event.rules && (
                  <div style={{ marginBottom: event.requirements ? 16 : 0 }}>
                    <h4 style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
                      <FiFileText color="#8b5cf6" /> Event Rules & Guidelines
                    </h4>
                    <p style={{ fontSize: 13.5, color: "var(--text-secondary)", whiteSpace: "pre-line", margin: 0 }}>
                      {event.rules}
                    </p>
                  </div>
                )}
                {event.requirements && (
                  <div>
                    <h4 style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
                      <FiCheckCircle color="#8b5cf6" /> Requirements & Eligibility
                    </h4>
                    <p style={{ fontSize: 13.5, color: "var(--text-secondary)", whiteSpace: "pre-line", margin: 0 }}>
                      {event.requirements}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* ORGANIZER / FACULTY INFO */}
            <div style={{ marginBottom: 30, padding: 20, borderRadius: 14, background: "var(--bg-base)", border: "1px solid var(--border-color)" }}>
              <h4 style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 700 }}>
                Organizer Information
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <FiUser color="#8b5cf6" size={18} />
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Faculty Organizer</div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{event.organizer_name || "Campus Faculty"}</div>
                  </div>
                </div>
                {event.organizer_department && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <FiBookOpen color="#8b5cf6" size={18} />
                    <div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Department</div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{event.organizer_department}</div>
                    </div>
                  </div>
                )}
                {event.organizer_email && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <FiMail color="#8b5cf6" size={18} />
                    <div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Email</div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{event.organizer_email}</div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* REGISTRATION ACTION / STATUS */}
            {registration ? (
              <div
                style={{
                  padding: 20,
                  borderRadius: 14,
                  background: "rgba(34, 197, 94, 0.1)",
                  border: "1px solid rgba(34, 197, 94, 0.3)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: 16,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <FiCheckCircle size={24} color="#22c55e" />
                  <div>
                    <div style={{ fontWeight: 700, color: "#22c55e" }}>
                      {registration.team_name ? `Registered with Team "${registration.team_name}"!` : "You are registered for this event!"}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                      Ticket #{registration.ticket_code} {registration.team_role ? `• ${registration.team_role.toUpperCase()}` : ""}
                    </div>
                  </div>
                </div>
                <button className="btn btn-primary btn-sm" onClick={() => setQrModal(registration)}>
                  View Digital Pass / QR
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                {event.registration_type !== "team" && (
                  <button
                    className="btn btn-primary"
                    disabled={event.available_seats <= 0 || registering || user?.role === "faculty"}
                    onClick={handleRegisterIndividual}
                  >
                    {event.available_seats <= 0
                      ? "Fully Booked"
                      : registering
                      ? "Registering..."
                      : user?.role === "faculty"
                      ? "Faculty cannot register"
                      : "Register Individually"}
                  </button>
                )}

                {event.registration_type !== "individual" && (
                  <button
                    className="btn btn-outline"
                    disabled={event.available_seats <= 0 || registering || user?.role === "faculty"}
                    onClick={openTeamModal}
                    style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
                  >
                    <FiUsers /> Register as Team
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TEAM REGISTRATION MODAL */}
      <Modal open={teamModalOpen} onClose={() => !teamSubmitting && setTeamModalOpen(false)} title="Team Registration" width={520}>
        <form onSubmit={handleSubmitTeam}>
          <div className="form-group">
            <label className="form-label">Team Name</label>
            <input
              className="form-input"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="e.g. Code Ninjas"
              required
            />
          </div>

          {/* Team Leader Badge */}
          <div style={{ marginBottom: 18, padding: "12px 16px", borderRadius: 12, background: "var(--bg-base)", border: "1px solid var(--border-color)" }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700, letterSpacing: 0.5, marginBottom: 4 }}>
              Team Leader (You)
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{user?.name}</div>
              <span className="badge badge-primary">{user?.registration_number || "Leader"}</span>
            </div>
          </div>

          {/* Team Member Search Input */}
          <div className="form-group">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <label className="form-label" style={{ margin: 0 }}>Add Team Members</label>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {teamMembers.length + 1} / {event?.max_team_size || 4} Members
              </span>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <div style={{ position: "relative", flex: 1 }}>
                <FiSearch style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                <input
                  className="form-input"
                  style={{ paddingLeft: 38 }}
                  value={searchRegNo}
                  onChange={(e) => {
                    setSearchRegNo(e.target.value);
                    setSearchError("");
                  }}
                  placeholder="Enter Student Reg Number (e.g. 21CS1045)"
                  disabled={teamMembers.length + 1 >= (event?.max_team_size || 4)}
                />
              </div>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={handleSearchAndAddMember}
                disabled={searchingStudent || !searchRegNo.trim() || teamMembers.length + 1 >= (event?.max_team_size || 4)}
                style={{ padding: "0 16px" }}
              >
                <FiPlus /> {searchingStudent ? "Searching..." : "Add"}
              </button>
            </div>

            {searchError && (
              <div style={{ color: "var(--danger)", fontSize: 12.5, marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <FiAlertCircle size={14} /> {searchError}
              </div>
            )}
          </div>

          {/* Added Members List */}
          {teamMembers.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
              {teamMembers.map((m) => (
                <div
                  key={m.registration_number}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 14px",
                    borderRadius: 10,
                    background: "var(--bg-glass)",
                    border: "1px solid var(--border-color)",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>{m.name}</div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {m.registration_number} • {m.department} (Sem {m.semester})
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveMember(m.registration_number)}
                    style={{ background: "none", border: "none", color: "var(--danger)", cursor: "pointer", padding: 4 }}
                  >
                    <FiTrash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 20 }}>
            <button type="button" className="btn btn-outline" onClick={() => setTeamModalOpen(false)} disabled={teamSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={teamSubmitting || !teamName.trim()}>
              {teamSubmitting ? "Registering Team..." : "Submit Team Registration"}
            </button>
          </div>
        </form>
      </Modal>

      {/* QR TICKET / PASS MODAL */}
      <Modal open={!!qrModal} onClose={() => setQrModal(null)} title="Digital Event Pass" width={400}>
        {qrModal && (
          <div style={{ textAlign: "center" }}>
            {qrModal.qr_code_path ? (
              <div style={{ background: "#ffffff", padding: 16, borderRadius: 16, display: "inline-block", marginBottom: 16 }}>
                <img
                  src={fileUrl(qrModal.qr_code_path)}
                  alt="QR Code Ticket"
                  style={{ width: 220, height: 220, objectFit: "contain", display: "block" }}
                />
              </div>
            ) : (
              <div style={{ padding: 24, color: "var(--text-muted)" }}>Generating QR Code...</div>
            )}
            <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>{event?.title}</h4>
            {qrModal.team_name && (
              <div className="badge badge-primary" style={{ marginBottom: 8 }}>
                Team: {qrModal.team_name} ({qrModal.team_role || "Member"})
              </div>
            )}
            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 14 }}>
              Ticket Code: <strong style={{ color: "#8b5cf6" }}>#{qrModal.ticket_code}</strong>
            </p>
            <button
              className="btn btn-outline btn-sm"
              style={{ width: "100%" }}
              onClick={() => registrationService.downloadSlip(qrModal.id)}
            >
              <FiDownload /> Download Pass PDF
            </button>
          </div>
        )}
      </Modal>
    </>
  );

  if (embedded) return content;

  return (
    <div>
      <PublicNavbar />
      <section className="container" style={{ padding: "40px 24px 90px" }}>{content}</section>
      <PublicFooter />

      <style>{`
        @media (max-width: 700px) {
          section .container div[style*="repeat(4, 1fr)"] { grid-template-columns: repeat(2, 1fr) !important; }
        }
      `}</style>
    </div>
  );
}

function InfoBlock({ icon, label, value }) {
  return (
    <div style={{ padding: 16, borderRadius: 14, background: "var(--bg-base)", border: "1px solid var(--border-color)" }}>
      <div style={{ color: "#8b5cf6", marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
